# coding=utf-8
__author__ = "Monstrofil"

RES_PACKAGES_PATH = '../../../../../res_packages/'
IDX_PACKAGES_PATH = '../../../idx/'


class PkgMgr:
    def __init__(self, pkg_name):
        self._pkg_name = pkg_name
        self._nodes_list = []
        self._nodes_by_id = {}
        self._nodes_by_name = {}
        self._nodes_by_name_tree = {}
        self._files = {}
        self._pkg_path = None
        self._load_idx()
        pass

    def get_node_by_name(self, id_):
        return self._nodes_by_name.get(id_)

    def get_node_by_id(self, id_):
        return self._nodes_by_id.get(id_)

    def _load_idx(self):
        idx_path = IDX_PACKAGES_PATH + '{0}.idx'.format(self._pkg_name)

        with open(idx_path, 'rb') as f:
            f.seek(16)
            items_amount = int(f.read(4)[::-1].encode('hex'), 16)
            files_amount = int(f.read(4)[::-1].encode('hex'), 16)

            f.seek(56)

            for i in xrange(items_amount):
                u1 = f.read(8).encode('hex')
                u2 = f.read(8).encode('hex')
                id_ = f.read(8).encode('hex')
                parent_id = f.read(8).encode('hex')

                node = Node(id_, parent_id, self)
                self._nodes_list.append(node)
                self._nodes_by_id[id_] = node

            for i in xrange(items_amount):
                s = ''
                j = f.read(1)
                while j != '\x00':
                    s += j
                    j = f.read(1)
                self._nodes_list[i].set_name(s)
                continue

            for i in xrange(files_amount):
                id_ = f.read(8).encode('hex')
                f.read(8)
                offset = int(f.read(4)[::-1].encode('hex'), 16)
                f.read(12)
                items_amount = int(f.read(4)[::-1].encode('hex'), 16)
                f.read(4)
                file_ = Location(offset, items_amount)
                self._files[id_] = file_
                f.read(8)
            f.read(24)
            self._pkg_path = RES_PACKAGES_PATH + f.read()[:-1]

        for node in self._nodes_list:
            self._nodes_by_name[node._name] = node
            if node.parent():
                node.parent().add_child(node)

    def _read_file_by_node(self, node):
        fileinfo = self._files.get(node._id)
        if fileinfo is None:
            return None

        with open(self._pkg_path, 'rb') as f:
            f.seek(fileinfo.offset)
            return f.read(fileinfo.size)

    def get_file_contents(self, filepath):
        components = filepath.split('/')
        root_node = self.get_node_by_name(components[0])
        for component in components[1:]:
            root_node = root_node.get_child_by_name(component)
            if root_node is None:
                return None
        return self._read_file_by_node(root_node)

    def clear(self):
        del self._nodes_list[:]
        self._nodes_by_id.clear()
        self._nodes_by_name.clear()
        self._nodes_by_name_tree.clear()
        self._files.clear()


class Node:
    def __init__(self, id_, parent_id, pkg_manager):
        self._pkg_manager = pkg_manager
        self._id = id_
        self._parent = parent_id
        self._name = None

        self._children = dict()

    def set_name(self, name):
        self._name = name

    def parent(self):
        return self._pkg_manager.get_node_by_id(self._parent)

    def get_child_by_name(self, name):
        return self._children.get(name)

    def add_child(self, child):
        self._children[child._name] = child

    def __str__(self):
        return '{0}:{1}:{2}'.format(self._id, self._parent, self._name)

    def __repr__(self):
        return str(self)


class Location:
    def __init__(self, offset, size):
        self.offset = offset
        self.size = size

    def __str__(self):
        return '{0}:{1}'.format(self.offset, self.size)

    def __repr__(self):
        return str(self)
