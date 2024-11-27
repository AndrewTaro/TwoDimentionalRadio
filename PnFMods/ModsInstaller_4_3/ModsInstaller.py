# coding=utf-8
import time
import xml
import re

from ResMgr import PkgMgr

mods_api = False
color = False
try:
    mod_path = utils.getModDir() + '/'
    et = xml.etree.ElementTree
    os = xml.sax.saxutils.os
    from xml.dom import minidom
    mods_api = True
except:
    import xml.etree.cElementTree as et
    import xml.dom.minidom as minidom
    import os
    import ctypes
    import platform
    
    mod_path = os.getcwd() + '/'    
    if int(platform.win32_ver()[0]) >= 10:
        color = True
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

INSTALLED_MODS = 'installed_mods.xml'
USS_SETTINGS = 'gui/uss_settings.xml'
ACTIONS = ['insert', 'remove', 'replace', 'rename', 'copy_past']
FIND = ['find_node', 'find_parent', 'position', 'default_position', 'do_if_exist', 'do_if_not_exist', 'remove', 'old',
        'rename', 'target_file']
ATTRS = ['className', 'name', 'type', 'value']

debug = 0
dev = False
pkg = None
wowsunpack = True if os.path.isfile(mod_path + 'wowsunpack.exe') and not mods_api else False


def logging(text, level=0):
    """Вывод в python.log"""
    global debug
    if debug >= level:
        text_node = '{:150.150}'.format(text.replace('R_split_string', ' ').replace('R_tab', ' ').replace('\t', ' '))
        if mods_api:
            utils.logInfo(text_node)
        else:
            if color:
                if '[ERROR]' in text_node:
                    print('\033[31m%s\033[0m' % text_node)
                elif 'already installed' in text_node or 'installed in' in text_node:
                    print('\033[32m%s\033[0m' % text_node)
                elif 'start action' in text_node:
                    print('\033[33m%s\033[0m' % text_node)
                elif 'search path' in text_node:
                    print('\033[36m%s\033[0m' % text_node)
                else:
                    print(text_node)
            else:
                print(text_node)


def iter_xml_files(view=False):
    """Получение списока файлов со скриптами"""
    mods = os.walk(mod_path + 'mods/')
    for dir_, folders, files in mods:
        for filename in files:
            if not filename.endswith('.xml'):
                if view:
                    logging('[WARNING]: extra file in mods directory %s' % filename)
                continue
            yield 'mods/' + filename


def compare(check_inst, check_mod, name):
    """Сравнение версий"""
    if check_inst == '':
        return False
    for a, b in zip(check_inst.split('.'), check_mod.split('.')):
        a = int(a) if a.isdigit() else a
        b = int(b) if b.isdigit() else b
        if a < b:
            logging('   [INFO]: installing an updated %s (old %s, new %s)'
                    % (name, check_inst, check_mod))
            return True
        if a > b:
            logging('[WARNING]: a newer mod is already installed. Skipping install.')
            return False
    return False


def get_text_child(node):
    """Генератор TEXT_NODE"""
    for child in node.childNodes:
        if child.nodeType == 3:
            yield child


def get_element_child(node, tag_name=''):
    """Генератор ELEMENT_NODE. Пропускает <attrs>, если не указано обратного"""
    for child in node.childNodes:
        if child.nodeType == 1:
            if (tag_name == '' and child.tagName.lower() != 'attrs') or child.tagName.lower() == tag_name.lower():
                yield child


def name_to_attr(attrs):
    """Поддержка скриптов от версии ModsInstaller v3.х
    Переименование type в attr_1, name в value_1, value в value_2 и добавление attr_2
    Приведение аргументов и значений к нижнему регистру"""
    if attrs.get('attr_rename'):
        pass
    for key in attrs.keys():
        key_lower = key.lower()
        if key_lower == 'type':
            attrs.update({'attr_1': attrs.pop(key)})
        elif key_lower == 'name':
            attrs.update({'value_1': attrs.pop(key)})
        elif key_lower == 'value':
            attrs.update({'value_2': attrs.pop(key)})
        else:
            attrs.update({key_lower: attrs.pop(key)})
    if attrs.get('value_2') and not attrs.get('attr_2'):
        attrs.update({'attr_2': 'value'})
    return attrs


class GetAttrs:
    """Получение атрибутов node"""
    def __init__(self, parent_node):
        tag = parent_node.tagName
        tag_lower = tag.lower()
        self.node = dict(parent_node.attributes.items())
        self.error = None
        if not self.node.get('number', '1').isdigit():
            self.error = '  [ERROR]: attribute number="%s" is not digit' % self.node.get('number')
            self.number = self.node.get('number')
            self.number_parent = 1
        else:
            self.number_parent = int(self.node.pop('number', 1)) if tag_lower == 'find_parent' else 1
            self.number = int(self.node.pop('number', 1))
        self.orig = True if self.node.pop('orig', 'false').lower() == 'true' else False
        self.clear = True if self.node.pop('clear', 'false').lower() == 'true' else False
        self.recursive = True if self.node.get('recursive', 'false').lower() == 'true' else False
        self.sub_nodes = True if self.node.get('sub_nodes', 'true').lower() == 'true' else False
        self.do_if_mod_installed = []
        self.do_if_mod_not_installed = []
        self.do_if_exist = None
        self.do_if_not_exist = None
        self.action = None
        self.find = None
        self.find_tag = tag
        self.position = None
        self.default_position = None
        self.copy_from = None
        self.rename = None
        self.cut = None
        self.log_info = ''
        log_info = self.node.pop('log_info', '')
        if tag_lower in ACTIONS + FIND:
            self.node = name_to_attr(self.node)
            self._get_log_info()
            if tag_lower in ACTIONS:
                self.action = tag_lower
                if tag_lower == 'insert':
                    position = parent_node.cloneNode(False)
                    position.tagName = 'position'
                    self.position = GetAttrs(position)
            if tag_lower in FIND:
                self.find = tag_lower
                self.find_tag = self.node.get('tag', '')
        else:
            self._get_log_info()
            self.sub_nodes = False
        log_info = self._get_from_attrs(parent_node, log_info)
        self.log_info += log_info if 'position' not in tag_lower else ''

    def _get_log_info(self):
        """Создание log_info"""
        self.log_info = self.find_tag
        if self.node.get('insert'):
            self.log_info += ' ' + self.node.get('insert')
        if (self.find_tag == 'default_position' or self.find_tag == 'position') and not self.node.get('insert'):
            self.log_info += ' bottom'
        self.log_info += ' '
        for attr in ATTRS:
            if self.node.get(attr):
                self.log_info += attr + '="' + self.node.get(attr) + '" '
        if self.node.get('tag'):
            self.log_info += self.node.get('tag') + ' '
        if self.node.get('attr_1'):
            self.log_info += self.node.get('attr_1') + '="' + self.node.get('value_1', '') + '" '
        if self.node.get('attr_2'):
            self.log_info += self.node.get('attr_2') + '="' + self.node.get('value_2', '') + '" '
        if self.node.get('text'):
            self.log_info += 'text="' + self.node.get('text') + '" '
        if self.number > 1:
            self.log_info += 'number="' + str(self.number) + '" '
        if self.number_parent > 1:
            self.log_info += 'number="' + str(self.number_parent) + '" '

    def _get_from_attrs(self, parent_node, log_info):
        """Обработка атрибутов из <attrs/>"""
        for attrs in get_element_child(parent_node, 'attrs'):
            for child in get_element_child(attrs):
                child_tag = child.tagName.lower()
                child_attrs = name_to_attr(dict(child.attributes.items()))
                if child_tag == 'do_if_mod_installed':
                    self.do_if_mod_installed.append(child.getAttribute('mod'))
                elif child_tag == 'do_if_mod_not_installed':
                    self.do_if_mod_not_installed.append(child.getAttribute('mod'))
                elif child_tag == 'log_info' and 'position' not in self.log_info:
                    log_info = child_attrs.get('value_2') + ' '
                elif child_tag == 'position':
                    self.position = GetAttrs(child)
                elif child_tag == 'default_position':
                    self.default_position = GetAttrs(child)
                elif child_tag == 'do_if_exist':
                    self.do_if_exist = GetAttrs(child)
                elif child_tag == 'do_if_not_exist':
                    self.do_if_not_exist = GetAttrs(child)
                elif child_tag == 'copy_from':
                    self.copy_from = child_attrs
                elif child_tag == 'rename':
                    self.rename = child_attrs
                elif child_tag == 'cut':
                    self.cut = True
        return log_info


def find_text_in_node(node, attrs):
    """Поиск текста в TEXT_NODE"""
    if attrs.node.get('text'):
        for child in get_text_child(node):
            if compare_attr(attrs.node.get('text'), child.data, attrs.node.get('strict_text', 'false')):
                return True
    else:
        return True


def compare_attr(attr1, attr2, strict):
    """Сравнение атрибутов с учётом строгости"""
    if attr1 is None:
        return
    for attr in attr1.split('//'):
        if strict == 'true':
            found = attr.strip() == attr2
        else:
            found = attr.strip() in attr2
        if not found:
            return
    return True


def find_node(node, attrs):
    """Поиск node"""
    if not attrs.find_tag:  # Если не нужен поиск, вернуть node
        yield node
    else:
        number = attrs.number
        # Получение списка поиска, в зависимости от sub_nodes
        find_list = node.getElementsByTagName(attrs.find_tag) \
            if attrs.sub_nodes else get_element_child(node, attrs.find_tag)
        # Перебор списка
        for child in find_list:
            if dict(child.attributes.items()) == attrs.node \
                    or (attrs.find and (compare_attr(attrs.node.get('value_1', ''),
                                                     child.getAttribute(attrs.node.get('attr_1')),
                                                     attrs.node.get('strict_1', 'false'))
                                        and compare_attr(attrs.node.get('value_2', ''),
                                                         child.getAttribute(attrs.node.get('attr_2')),
                                                         attrs.node.get('strict_2', 'false'))
                                        and find_text_in_node(child, attrs))):
                if number == 1:
                    yield child
                    if not attrs.recursive:
                        break
                else:
                    number -= 1


def add_child(file_node):
    """Создание вложенной пустой Text_Node, если не было 'детей'"""
    if not file_node.hasChildNodes():
        child = minidom.Document().createTextNode('')
        file_node.appendChild(child)


def get_position(node_attrs, file_node):
    """Поиск позиции вставки для insert"""
    position = node_attrs.position if node_attrs.find != 'default_position' else node_attrs
    if position:  # Если ищем position или default_position
        logging('  [DEBUG]: search insert %s' % position.log_info, 3)
        found = False
        insert = position.node.get('insert', '').lower()
        add_child(file_node)
        if not position.node.get('insert'):
            found = True
            yield file_node.lastChild
        elif insert == 'top':
            found = True
            yield file_node.firstChild
        else:
            for insert_position in find_node(file_node, position):
                found = True
                if insert == 'before_node':
                    yield insert_position.previousSibling
                elif insert == 'after_node':
                    yield insert_position.nextSibling
                elif insert == 'before_parent':
                    yield insert_position.parentNode.previousSibling
                elif insert == 'after_parent':
                    yield insert_position.parentNode.nextSibling
                else:
                    yield file_node.lastChild
        if not found:
            if node_attrs.default_position:  # Ищем default_position, если она есть
                logging('[WARNING]: not found %s' % position.log_info, 3)
                for default_position in get_position(node_attrs.default_position, file_node):
                    yield default_position
            else:
                logging('  [ERROR]: not found %s' % position.log_info)
    elif node_attrs.action == 'replace':  # Для replace возвращаем исходную node
        yield file_node
    else:
        yield file_node.lastChild  # Если нет insert="top" и т.д., возвращаем lastChild


def check_file_name(file_name):
    path = os.path.abspath(mod_path + '../../' + file_name).replace('\\', '/')
    if 'res_mods' in path:
        return path.split('res_mods/')[-1]


class IterTargetFile:
    """Обработка файлов в скрипте"""
    def __init__(self, script_file, node_target_file, attrs_target_file, file_name, doms_orig):
        self.doms_orig = doms_orig
        self._script_file = script_file
        self._node_target_file = node_target_file
        # Если файл уже изменялся модом, то открываем из списка сохранения.
        # Если нет - открываем новый, если нет orig="true"
        checked_file_name = check_file_name(file_name)
        if not checked_file_name:
            logging('  [ERROR]: file %s not in res_mods' % file_name)
            self._script_file.error = True
            return
        self._file = script_file.save_list.get(checked_file_name)
        if not self._file or attrs_target_file.orig:
            self._file = File(checked_file_name, attrs_target_file).get_dom()
            if self._file.error:
                self._script_file.error = True
                return
        if not self._do_if(attrs_target_file, self._file.data_dom.documentElement):
            return
        for root_node in get_element_child(node_target_file, 'root_node'):
            for script_node, file_node in self._iter_node(root_node, self._file.data_dom.documentElement):
                self._action(script_node, file_node)
        if self._script_file.saving:  # Если вносились изменения, добавляем файл в сейв лист
            script_file.save_list.update({checked_file_name: self._file})

    def find_node_path(self, dom, attrs):
        """Поиск пути"""
        if attrs.action:  # Если Это действие, то возвращаем dom
            yield dom
        else:
            logging('  [DEBUG]: search path %s ' % attrs.log_info, 3)
            if not self._do_if(attrs, dom):
                return
            if attrs.error:
                logging(attrs.error)
                self._script_file.error = True
                return
            found = False
            for path in find_node(dom, attrs):  # Ищем путь в редактируемом файле
                if attrs.find == 'find_parent':
                    number = attrs.number_parent
                    while number > 0:
                        path = path.parentNode
                        if path is path.ownerDocument.documentElement:
                            logging('  [ERROR]: during %s on step %s found document root' % (
                                attrs.log_info, attrs.number_parent - number + 1))
                            self._script_file.error = True
                            break
                        number -= 1
                if self._script_file.error:
                    break
                found = True
                yield path
            if not found:
                logging('  [ERROR]: not found %s' % attrs.log_info)
                self._script_file.error = True

    def _iter_node(self, script_node, file_node):
        """Перебор путей"""
        script_node_attrs = GetAttrs(script_node)
        # if self._do_if(script_node_attrs, file_node) and not self._script_file.error:  # Нужно ли искать путь
        if not self._script_file.error:  # Нужно ли искать путь
            if script_node_attrs.find_tag.lower() == 'root_node' or script_node_attrs.find_tag.lower() == 'copy':
                logging('  [DEBUG]: search path root', 3)
            if script_node_attrs.action or not script_node.hasChildNodes():
                # Если найдено действие, либо нет 'детей', возвращаем script_node, file_node
                yield script_node, file_node
            else:
                # Перебор 'детей'
                for child_node in get_element_child(script_node):
                    if self._script_file.error:
                        break
                    child_node_attrs = GetAttrs(child_node)
                    # Поиск путей 'ребёнка'
                    for path in self.find_node_path(file_node, child_node_attrs):
                        if self._script_file.error:
                            break
                        # Перебор путей 'ребёнка'
                        for _script_node, _file_node in self._iter_node(child_node, path):
                            yield _script_node, _file_node  # Возвращение найденных путей

    def _action(self, node, file_node):
        """Определение типа действия"""
        node_attrs = GetAttrs(node)
        if not node_attrs.action or not self._do_if(node_attrs, file_node):
            return
        logging('  [DEBUG]: start action %s' % node_attrs.log_info, 1)
        if node_attrs.action == 'insert':
            self._insert(node, node_attrs, file_node)
        if node_attrs.action == 'copy_past':
            self._copy_past(node, node_attrs, file_node)
        if node_attrs.action == 'rename':
            for rename_node in find_node(file_node, node_attrs):
                self._rename(node_attrs.node, rename_node)
        if node_attrs.action == 'remove':
            self._remove(node_attrs, file_node)
        if node_attrs.action == 'replace':
            self._replace(node, node_attrs, file_node)

    def _do_if(self, attrs, file_node):
        """Проверка, нужно ли выполнять действие"""
        if attrs.do_if_mod_installed or attrs.do_if_mod_not_installed or attrs.do_if_exist or attrs.do_if_not_exist:
            if attrs.do_if_mod_installed:
                for mod in attrs.do_if_mod_installed:
                    logging('  [DEBUG]: do %sif mod %s installed?' % (attrs.log_info, mod), 3)
                    if self._script_file.other_mods.get(mod):
                        break
                else:
                    logging('  [DEBUG]: not', 3)
                    return
            if attrs.do_if_mod_not_installed:
                for mod in attrs.do_if_mod_not_installed:
                    logging('  [DEBUG]: do %s if mod %s not installed?' % (attrs.log_info, mod), 3)
                    if self._script_file.other_mods.get(mod):
                        logging('  [DEBUG]: not', 3)
                        return
            elif attrs.do_if_exist:
                logging('  [DEBUG]: do %sif%s exist?' %
                        (attrs.log_info, attrs.do_if_exist.log_info.replace('do_if_exist', '')), 3)
                found = False
                for i in find_node(file_node, attrs.do_if_exist):
                    found = True
                if not found:
                    logging('  [DEBUG]: not', 3)
                    return                
            elif attrs.do_if_not_exist:
                logging('  [DEBUG]: do %sif%snot exist?' %
                        (attrs.log_info, attrs.do_if_not_exist.log_info.replace('do_if_not_exist', '')), 3)
                for i in find_node(file_node, attrs.do_if_not_exist):
                    logging('  [DEBUG]: not', 3)
                    return                
            logging('  [DEBUG]: do', 3)
        return True

    def _insert(self, node, node_attrs, file_node):
        """Действие insert"""
        found = False
        # Перебор позицый для вставки
        for insert_position in get_position(node_attrs, file_node):
            # Перебор node из <insert>
            for insert_node in node.childNodes:
                if insert_node.nodeType == 1:
                    if insert_node.tagName.lower() == 'attrs':
                        continue
                    logging('  [DEBUG]: insert %s' % GetAttrs(insert_node).log_info, 2)
                insert_node_clone = insert_node.cloneNode(True)
                insert_position.parentNode.insertBefore(insert_node_clone, insert_position)
            found = True
            self._script_file.saving = True
        if not found:
            self._script_file.error = True

    def _copy_past(self, node, node_attrs, file_node):
        """Действие copy_past"""
        # Определение источника копирования
        if node_attrs.copy_from:
            if node_attrs.copy_from.get('orig', 'false').lower() == 'true':
                copy_from_node = self.doms_orig.get(node_attrs.copy_from.get('file'))
                copy_from_node = copy_from_node.data_dom_orig
            else:
                copy_from_file = File(node_attrs.copy_from.get('file')).get_dom()
                if copy_from_file.error:
                    return
                copy_from_node = copy_from_file.data_dom
        else:
            copy_from_node = self._file.data_dom
        # Перебор позиций для вставки
        for insert_position in get_position(node_attrs, file_node):
            # Перебор <copy>
            for copy in get_element_child(node, 'copy'):
                # Перебор найденных путей для копирования
                for node_in_script, node_cut in self._iter_node(copy, copy_from_node.documentElement):
                    logging('  [DEBUG]: past %s' % GetAttrs(node_cut).log_info, 2)
                    node_clone = node_cut.cloneNode(True)
                    # Переименование содержимого атрибутов
                    if node_attrs.rename:
                        self._rename(node_attrs.rename, node_clone)
                    insert_position.parentNode.insertBefore(node_clone, insert_position)
                    # Удаление в источенике
                    if node_attrs.cut:
                        logging('  [DEBUG]: remove %sfrom source' % GetAttrs(node_cut).log_info, 2)
                        node_cut.parentNode.removeChild(node_cut)
                    self._script_file.saving = True

    def _rename(self, node, node_cut):
        """Действие rename"""
        attr_rename = node.get('attr_rename')
        attr_rename_value = node_cut.getAttribute(attr_rename)
        old_value = node.get('old_value', attr_rename_value)
        new_value = node.get('new_value')
        if not attr_rename:
            logging('  [ERROR]: not found "attr_rename" in rename %s' % node.items())
            self._script_file.error = True
            return
        if not new_value:
            logging('  [ERROR]: not found "new_value" in rename %s' % node.items())
            self._script_file.error = True
            return
        if old_value in attr_rename_value:
            logging('  [DEBUG]: rename in %s "%s" to "%s"' % (attr_rename, old_value, new_value), 2)
            node_cut.setAttribute(attr_rename, attr_rename_value.replace(old_value, new_value))
            self._script_file.saving = True

    def _remove(self, node_attrs, file_node):
        """Действие remove"""
        remove = False
        for remove_node in find_node(file_node, node_attrs):
            logging('  [DEBUG]: %s%s' % ('recursive ' if node_attrs.recursive else '', node_attrs.log_info), 2)
            remove_node.parentNode.removeChild(remove_node)
            self._script_file.saving = True
            remove = True
        if not remove:
            logging('[WARNING]: nothing to remove', 2)

    def _replace(self, node, node_attrs, file_node):
        """Действие replace"""
        insert_nodes = [file_node.nextSibling]
        old = False
        # Перебор <old>
        for node_old_in_script in get_element_child(node, 'old'):
            old = True
            node_old_in_script_attrs = GetAttrs(node_old_in_script)
            logging('  [DEBUG]: %ssearch node to replace %s' %
                    ('recursive ' if node_old_in_script_attrs.recursive else '',
                     node_old_in_script_attrs.log_info.replace('old ', '')), 3)
            found = False
            # Перебор найденных old
            insert_nodes = []
            for node_old_in_file in find_node(file_node, node_old_in_script_attrs):
                logging('  [DEBUG]: remove %s' % node_old_in_script_attrs.log_info.replace('old ', ''), 2)
                insert_nodes.append(node_old_in_file.nextSibling)
                node_old_in_file.parentNode.removeChild(node_old_in_file)
                found = True
            if not found:
                logging('  [ERROR]: not found %s' % node_old_in_script_attrs.log_info)
                self._script_file.error = True
                return
        if not old:
            logging('  [DEBUG]: %sremove %s' % ('recursive ' if node_attrs.recursive else '',
                                                GetAttrs(node.parentNode).log_info), 2)
            file_node.parentNode.removeChild(file_node)
        # Вставка из <new>
        for node_new in get_element_child(node, 'new'):
            for insert_node in insert_nodes:
                self._insert(node_new, node_attrs, insert_node)


class ModsInstaller:
    """Установка модов"""
    def __init__(self, mi_version):
        self.error = 0
        self.skip = 0
        self.update = 0
        self.all = 0
        self.installed = 0
        self.doms_orig = {}
        self.script_file = None
        self.uss_settings = None
        self.watch_update = {}
        self.mi_version = mi_version
        del_unpack()
        self._run(iter_xml_files(True))
        self._run(self._update_list())
        if pkg:
            pkg.clear()
        del_unpack()

    def _run(self, _iter_xml_files):
        """Перебор файлов со скриптами"""
        for filename in _iter_xml_files:
            self.all += 1
            time_start_install = time.time()
            logging('   [INFO]: processing mod %s' % filename.replace('mods/', ''))
            self.script_file = File(filename, path='').get_et(False)  # Чтение и парсинг скрипта
            if self.script_file.error:
                self.error += 1
                logging('  [ERROR]: unable to parse mod file %s. Skipping install.' % filename.replace('mods/', ''))
                continue
            check = Check(self)
            # Проверка, нужна ли установка
            if not check.install_mod:
                if self.script_file.error:
                    self.error += 1
                else:
                    self.skip += 1
                continue
            # Обновление словаря doms_orig
            check.get_orig()
            if self.script_file.error:
                return
            # Добавление installed_mods.xml в список сохранения
            self.script_file.get_dom().save_list.update({INSTALLED_MODS: check.write()})
            # Перебор target_File в скрипте
            for node_target_file in get_element_child(self.script_file.data_dom.documentElement, 'target_File'):
                attrs_target_file = GetAttrs(node_target_file)
                # Перебор файлов в target_File
                if not attrs_target_file.node.get('file'):
                    logging('  [ERROR]: not found "file" in target_file %s' % attrs_target_file.node.values())
                    self.script_file.error = True
                    return
                for file_name in attrs_target_file.node.get('file').split(','):
                    logging('  [DEBUG]: processing file ' + file_name, 1)
                    IterTargetFile(
                        self.script_file, node_target_file, attrs_target_file, file_name.strip(), self.doms_orig)
            if self.script_file.error:
                logging('  [ERROR]: skipping install ' + filename.replace('mods/', ''))
                self.error += 1
                continue
            if self.script_file.update:
                self.update += 1
            else:
                self.installed += 1
            # Сохранение файлов из сейв листа
            for _file in self.script_file.save_list.values():
                if not os.path.isdir((mod_path + '../../' + _file.file_name).rpartition('/')[0]):
                    os.makedirs((mod_path + '../../' + _file.file_name).rpartition('/')[0])
                logging('  [DEBUG]: saving file ' + _file.file_name, 2)
                _file.save_xml_file()
            logging('   [INFO]: mod %s successfully installed in %s sec' %
                    (filename.replace('mods/', ''), (round(time.time() - time_start_install, 1))))

    def _update_list(self):
        """"Генератор содержащий моды, требующие обновления"""
        for mod, scripts in self.watch_update.items():
            uss_settings_file = File(USS_SETTINGS).get_et(False)
            if uss_settings_file.error:
                return
            uss_settings = uss_settings_file.data_et
            # Перебор строк с модами внутри uss_settings.xml
            for file_in_uss in uss_settings.findall('.mods/'):
                if mod in file_in_uss.text:
                    for script in scripts:
                        yield script

    def __del__(self):
        for _file in self.doms_orig.values():
            _file.data_dom_orig.unlink()
        self.doms_orig.clear()
        if os.path.exists(mod_path + 'ResMgr.pyc'):
            os.remove(mod_path + 'ResMgr.pyc')
        if os.path.exists(mod_path + 'ModsInstaller.pyc'):
            os.remove(mod_path + 'ModsInstaller.pyc')


def del_unpack():
    """Удаление папки с распакованными файлами"""
    if os.path.exists(mod_path + 'unpack'):
        os.system(mod_path + 'rmdir /S /Q unpack')


class Check:
    """Проверка, нужна ли установка мода"""
    def __init__(self, mi):
        self._mi = mi
        self.script_file = mi.script_file
        self.install_mod = False
        global debug, dev
        dev = False
        debug = 0
        # Парсинг installed_mods.xml
        self._file_installed_mods = File(INSTALLED_MODS).get_et(False)
        if self._file_installed_mods.error:
            logging('  [ERROR]: Unable parse installed_mods.xml. Skipping install')
            return
        # Поиск check в файле мода
        self._check_in_script = self.script_file.data_et.find('check')
        if self._check_in_script is None:
            logging(
                '  [ERROR]: missing <check/> in mod file ' + self.script_file.file_name.replace('mods/', '')
                + '. Skipping install')
            self.script_file.error = True
            return
        if not self._check_in_script.get('name'):
            logging('  [ERROR]: missing "name" in <check/>')
            self.script_file.error = True
            return
        self._check_in_script_attrs = self._check_in_script.attrib
        # Проверка режима разработки
        if self._check_in_script_attrs.pop('dev', '').lower() == 'true':
            logging('   [INFO]: developer mode')
            debug = 3
            dev = True
        # Проверка режима дебага
        debug = self._check_in_script_attrs.pop('debug', str(debug))
        if debug.isdigit():
            debug = int(debug)
            if debug > 0:
                logging('   [INFO]: debug level %s' % debug)
        else:
            debug = 3
            logging('   [INFO]: debug level 3')
        self.mod_in_installed = self._file_installed_mods.data_et.find(
            "mod[@name='%s']" % self._check_in_script_attrs.get('name'))
        # Проверка установлены ли зависимые моды
        self._check_exist_mode()
        if self.script_file.error:
            return
        # Проверка, установлен ли мод
        if self.mod_in_installed is None:
            self.install_mod = True
            self._mod_in_installed_attrs = {}
            return
        self._mod_in_installed_attrs = self.mod_in_installed.attrib
        # Сравнение версий МодИнсталлера и мода
        if compare(self._mod_in_installed_attrs.get('installer', ''), self._mi.mi_version, 'ModsInstaller') or \
                compare(self._mod_in_installed_attrs.get('version', ''), self._check_in_script_attrs.get('version', ''),
                        'mod'):
            self.script_file.update = True
            self.install_mod = True
            return
        if not self._installed_other_mod() and not dev:
            logging('   [INFO]: mod %s already installed. Pass' % self.script_file.file_name.replace('mods/', ''))
            return
        self.install_mod = True
        return

    def _installed_other_mod(self):
        """Нужно ли обновление, из-за установки другого мода"""
        for name, install in self.script_file.other_mods.items():
            if install and self._mod_in_installed_attrs.get(name, 'false') == 'false':
                logging('   [INFO]: updating after install %s' % name)
                self.script_file.update = True
                return True

    def _check_exist_mode(self):
        """Проверка, установлен ли зависимый мод"""
        uss_settings = None
        # Перебор модов внутри <check>
        for mod in self._check_in_script:
            if not mod.get('file'):
                logging('  [ERROR]: not found "file" in %s %s' % (mod.tag, mod.items()))
                self.script_file.error = True
                return
            if uss_settings is None:
                uss_settings_file = File(USS_SETTINGS).get_et(False)
                if uss_settings_file.error:
                    return
                uss_settings = uss_settings_file.data_et
            # Перебор строк с модами внутри uss_settings.xml
            for file_in_uss in uss_settings.findall('.mods/'):
                if mod.get('file') in file_in_uss.text:
                    self.script_file.other_mods.update({mod.tag: True})
                    break
            else:
                self.script_file.other_mods.update({mod.tag: False})
                update_watch_list = self._mi.watch_update.get(mod.get('file'), [])
                update_watch_list.append(self.script_file.file_name)
                self._mi.watch_update.update({mod.get('file'): update_watch_list})

    def get_orig(self):
        """Обновление словаря doms_orig"""
        if wowsunpack:  # Если найден wowsunpack.exe, распаковываем файлы
            if not os.path.exists(mod_path + 'unpack'):
                unpack_list = '-I gui/uss_settings.xml'
                for script in iter_xml_files():
                    script_et = et.parse(script)
                    for target_files in script_et.findall(".//target_File"):
                        unpack_list += ''.join(' -I ' + target_file.strip()
                                               for target_file in target_files.get('file').split(',')
                                               if target_file not in unpack_list)
                    unpack_list += ''.join(' -I ' + target_file.get('file')
                                           for target_file in script_et.findall(".//copy_from[@orig='true']")
                                           if target_file.get('file') not in unpack_list)
                os.system('wowsunpack.exe -x ../../../idx -p ../../../res_packages %s -o unpack' % unpack_list)
        # Перебор copy_from, содержащих orig="true"
        for copy_from in self.script_file.data_et.findall(".//copy_from[@orig='true']"):
            if not copy_from.get('file'):
                logging('  [ERROR]: not found "file" in copy_from %s' % copy_from.items())
                self.script_file.error = True
                return
            if not self._mi.doms_orig.get(copy_from.get('file')):
                # Если файл ещё не парсился, делаем это и сохраняем в doms_orig
                file_orig = File(copy_from.get('file'), orig=True).get_et(False)
                if file_orig.error:
                    return
                file_orig.data_dom_orig = minidom.parseString('<ui/>')
                self._mi.doms_orig.update({copy_from.get('file'): file_orig})
            # Перебор блоков из <copy>
            for node in self.script_file.data_et.findall(".//copy_from[@orig='true']..../copy/block"):
                find_string = "./block[@className='%s']" % node.get('className')
                found_node = self._mi.doms_orig.get(copy_from.get('file')).data_et.find(find_string)
                if found_node is None:
                    break
                data_copy = et.tostring(found_node)
                copy_node = minidom.parseString(data_copy).firstChild.cloneNode(True)
                self._mi.doms_orig.get(copy_from.get('file')).data_dom_orig.documentElement.appendChild(copy_node)

    def write(self):
        """Внесение изменений в installed_mods.xml"""
        # Удаление из installed_mods.xml всех записей с модом
        for remove in self._file_installed_mods.data_et.findall(
                "./mod[@name='%s']" % self._mod_in_installed_attrs.get('name')):
            self._file_installed_mods.data_et.remove(remove)
        self._check_in_script_attrs.update({"installer": self._mi.mi_version})
        add = self._file_installed_mods.data_et.makeelement('mod', self._check_in_script_attrs)
        for mod, install in self.script_file.other_mods.items():
            if install:
                add.set(mod, 'true')
        self._file_installed_mods.data_et.append(add)
        out_data = et.tostring(self._file_installed_mods.data_et)
        self._file_installed_mods.data_dom = minidom.parseString(out_data)
        return self._file_installed_mods


class File:
    """Чтение, парсинг и запись файлов"""
    def __init__(self, file_name, attrs=None, clear=False, orig=False, path='../../'):
        if attrs is None:
            self.clear = clear
            self.orig = orig
        else:
            self.clear = attrs.clear
            self.orig = attrs.orig
        self.path = path
        self.data = None
        self.data_et = None
        self.data_dom = None
        self.error = False
        self.data_dom_orig = None
        self.save_list = {}
        self.other_mods = {}
        self.file_name = file_name
        self.saving = False
        self.update = False

    def _format_multilines(self):
        """Замена внутри ="...." табов и переносов строк на R_tab и R_split_string"""
        self.data = ''.join(
            line.replace('\t', 'R_tab').replace('\n', 'R_split_string') if line.startswith('="')
            else line
            for line in
            re.split('(<!--.*?-->|=".*?")', self.data.replace('\r\n', '\n').replace('\r', '\n'), flags=re.DOTALL)
        )

    def _read_file(self, view):
        """Чтение файла"""
        if self.clear:  # Чистый файл
            if view:
                logging('  [DEBUG]: create clear file %s' % self.file_name, 3)
            self.data = '<ui>\n</ui>'
        elif self.orig:  # Распаковка файла из клиента
            if view:
                logging('  [DEBUG]: unpack original file %s' % self.file_name, 3)
            self._unpack(view)
            if self.data is None:
                logging('  [ERROR]: not found %s to extract' % self.file_name)
                self.error = True
                return
        elif os.path.isfile(mod_path + self.path + self.file_name):  # Существующий файл
            if view:
                logging('  [DEBUG]: open exist file %s' % self.file_name, 3)
            try:
                with open(mod_path + self.path + self.file_name, 'r') as f:
                    self.data = f.read()
            except:
                logging('  [ERROR]: unable open file %s' % self.file_name)
                self.error = True
        elif self.file_name == INSTALLED_MODS:
            self.data = '<data>\n</data>'
        else:  # Файла нет, распаковка из клиента
            if view:
                logging('  [DEBUG]: try unpack file %s' % self.file_name, 3)
            self._unpack(False)
            if self.data is None:  # В клиенте файла нет, создаём пустой
                if view:
                    logging('  [DEBUG]: unable unpack file %s, create clear' % self.file_name, 3)
                self.data = '<ui>\n</ui>'
        self._format_multilines()

    def _unpack(self, view):
        """Распаковка файла из клиента"""
        res = os.path.isfile('../../../res/' + self.file_name)
        path = '../../../res/' if res else 'unpack/'
        if not wowsunpack and not res:
            global pkg
            if not pkg:
                pkg = PkgMgr('gui')
            self.data = pkg.get_file_contents(self.file_name)
            return
        try:
            with open(mod_path + path + self.file_name, 'r') as f:
                self.data = f.read()
        except:
            if view:
                logging('  [ERROR]: unable open file %s' % self.file_name)

    def get_et(self, view=True):
        """et парсинг self.data"""
        if self.data is None:
            self._read_file(view)
            if self.error:
                return
        try:
            self.data_et = et.fromstring(self.data)
        except:
            self.error = True
            logging('  [ERROR]: unable parse file %s' % self.file_name)
            return
        return self

    def get_dom(self, view=True):
        """minidom  парсинг self.data"""
        if self.data is None:
            self._read_file(view)
            if self.error:
                return
        try:
            self.data_dom = minidom.parseString(self.data)
        except:
            self.error = True
            logging('  [ERROR]: unable parse file %s' % self.file_name)
            return
        return self

    def get_pretty_xml_string(self):
        r"""Удаление лишних \n из xml"""
        return ('\n'.join(
            line for line in
            self.data_dom.toprettyxml().split('\n')
            if line.strip()
        ))

    def save_xml_file(self):
        r"""Сохранение xml файла с заменой R_split_string и R_tab на \n и \t"""
        with open(mod_path + '../../' + self.file_name, 'w') as f:
            f.write(self.get_pretty_xml_string().encode('utf-8')
                    .replace('R_split_string', '\n').replace('R_tab', '\t'))

    def __del__(self):
        if self.data:
            del self.data
        if self.data_dom:
            self.data_dom.unlink()
        if self.data_et is not None:
            self.data_et.clear()
        if self.data_dom_orig:
            self.data_dom_orig.unlink()
