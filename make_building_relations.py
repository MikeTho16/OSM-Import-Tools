""" Takes a file of OSM data in XML format which contains building parts.
One or more building parts, may share a building ID, and this is used
to join multiple parts into a OSM building relation. For each relation
created, a building outline is created by unioning together all of the
parts. This is added to the relation with a role of "outline."

Running:

Instructions for running with 32 bit Python 2.7 under Windows.

Download Shapely-1.5.17-cp27-cp27m-win32.whl from http://www.lfd.uci.edu/~gohlke/pythonlibs/#shapely
pip install Shapely-1.5.17-cp27-cp27m-win32.whl
python make_building_relations.py in.osm out.osm bldg_id_key

"""
import sys
from xml.etree.ElementTree import XMLParser
import argparse
from shapely.geometry import Polygon
from shapely.geometry import MultiPolygon
from shapely.ops import polygonize
from shapely.ops import cascaded_union


__version__ = '1.0.0.0'

class Node(object):
    """ Represents an OSM Node

    Attributes:
        osm_id - The OSM ID of the node.
        lat - The latitude of the node.
        lon - The longitude of the node.
        tags - Dictionary of tags of the way, keyed by the tag's key.
    """


    def __init__(self, osm_id, lat, lon):
        """ Initializes a new node.

        Inputs:
            osm_id - OSM id of the new node.
            lat - Latitude of the new node.
            lon - Longitude of the new node.

        Output:
            <nothing>
        """
        self.osm_id = osm_id
        self.lat = lat
        self.lon = lon
        self.tags = {}


    def add_tag(self, key, value):
        """ Add a tag to the node.

        Inputs:
            key - The key of the tag to be added.
            value - the value of the tag to be added.
        """
        self.tags[key] = value


    def write_xml(self, xml_out):
        """ Writes out the node in XML format.

        Inputs:
            xml_out - File object to which the xml will be written

        Outputs:
            <nothing>
        """
        if self.tags:
            xml_out.write('<node id="{}" lat="{}" lon="{}" visible="true">\n'
                          .format(self.osm_id, self.lat, self.lon))
            for key, value in self.tags.iteritems():
                xml_out.write('    <tag k="{}" v="{}" />\n'.format(key, value))
            xml_out.write('</node>\n')
        else:
            xml_out.write('<node id="{}" lat="{}" lon="{}" visible="true" />\n'
                          .format(self.osm_id, self.lat, self.lon))



class Nodes(object):
    """ Collection of OSM nodes.

    Attributes:
        _nodes - Dictionary, keyed by OSM ID, of the nodes in the collection.
        _nodes_by_lat_lon - Dictionary, keyed by (lat, lon), of the nodes in
            the collection.
        _lowest_id - the lowest OSM ID of any node in the collection. This
            is used to determine the ID of a new node.
    """


    def __init__(self):
        """ Initializes the collection of nodes.

        Inputs:
            <nothing>

        Outputs:
            <nothing>
        """
        self.nodes = {}
        self.nodes_by_lat_lon = {}
        self._lowest_id = -1


    def add(self, node):
        """ Add an existing node to the collection.

        Inputs:
            node - The Node object to be added to the collection.

        Outputs:
            <nothing>
        """
        self.nodes[node.osm_id] = node
        self.nodes_by_lat_lon[(float(node.lat), float(node.lon))] = node
        if int(node.osm_id) < self._lowest_id:
            self._lowest_id = int(node.osm_id)


    def __iter__(self):
        for _, node in self.nodes.iteritems():
            yield node


    def add_new(self, lat, lon):
        """ Create and add a new node to the collection.

        Inputs:
            lat - The latitude of the node to be created and added.
            lon - The longitude of the node to be created and added.

        Outputs:
            <nothing>
        """
        self._lowest_id -= 1
        new_node = Node(str(self._lowest_id), lat, lon)
        self.add(new_node)
        return new_node


    def add_new_if_not_exist(self, lat, lon):
        """ Creates and adds a node if there is not already one in the
        collection at the specified location.

        Inputs:
            lat - The latitude of the node to be created.
            lon - The longitude of the node to be created.

        Outputs:
            If a new node was created, it is returned, if a node at the
                specified location already exists, it is returned.
        """
        if (float(lat), float(lon)) in self.nodes_by_lat_lon:
            return self.nodes_by_lat_lon[(float(lat), float(lon))]
        return self.add_new(str(lat), str(lon))


    def write_xml(self, xml_out):
        """ Writes out the nodes in order from highest to lowest OSM id in
        XML format.

        Inputs:
            xml_out - file object which the xml will be written

        Outputs:
            <nothing>
        """
        for key in sorted(self.nodes, key=int, reverse=True):
            self.nodes[key].write_xml(xml_out)


    def __getitem__(self, key):
        return self.nodes[key]



class Way(object):
    """ Represents an OSM Way

    Attributes:
        osm_id - The OSM ID of the way.
        tags - Dictionary of tags of the way, keyed by the tag's key.
        _nodes - List of the nodes that make up the way.
    """


    def __init__(self, osm_id):
        """ Initializes the way object.

        Inputs:
            osm_id - The id of the way to be initialized.

        Output:
            <nothing>
        """
        self.osm_id = osm_id
        self.tags = {}
        self.nodes = []


    def add_tag(self, key, value):
        """ Add a tag to the way.

        Inputs:
            key - The key of the tag to be added.
            value - The value of the tag to be added.
        """
        self.tags[key] = value


    def delete_tag(self, key):
        """ Delete a tag from the way

        Inputs:
            key - The key of the tag to be deleted.
        """
        del self.tags[key]


    def add_node(self, node):
        """ Add a node to the way.

        Inputs:
            node - Actual node object, to be added to the way.

        Output:
            <nothing>
        """
        self.nodes.append(node)


    def write_xml(self, xml_out):
        """ Writes out the way in XML format.

        Inputs:
            xml_out - file object which the xml will be written

        Outputs:
            <nothing>
        """
        xml_out.write('<way id="{}" visible="true">\n'.format(self.osm_id))
        for node in self.nodes:
            xml_out.write('    <nd ref="{}" />\n'.format(node.osm_id))
        for key, value in self.tags.iteritems():
            xml_out.write('    <tag k="{}" v="{}" />\n'.format(key, value))
        xml_out.write('</way>\n')



class Ways(object):
    """ Collection of OSM ways.

    Attributes:
        _ways = Dictionary, keyed by OSM ID, of the ways in the collection.
        _lowest_id = the lowest OSM ID of any way in the collection. This
            is used to determine the ID of a new way.
    """


    def __init__(self):
        """ Initialize the colleciton of ways
        """
        self._ways = {}
        self._lowest_id = -1


    def add(self, way):
        """ Add an additional way to the collection.

        Inputs:
            way - The way object to be added to the collection.

        Output:
            <nothing>
        """
        self._ways[way.osm_id] = way
        if int(way.osm_id) < self._lowest_id:
            self._lowest_id = int(way.osm_id)


    def add_new(self):
        """ Create and add a new relation to the collection.

        Inputs:
            <nothing>

        Output:
            The new way.
        """
        self._lowest_id -= 1
        new_way = Way(self._lowest_id)
        self.add(new_way)
        return new_way


    def write_xml(self, xml_out):
        """ Writes out the ways in order from highest to lowest OSM id in
        XML format.

        Inputs:
            xml_out - file object which the xml will be written

        Outputs:
            <nothing>
        """
        for key in sorted(self._ways, key=int, reverse=True):
            self._ways[key].write_xml(xml_out)


    def __iter__(self):
        for _, way in self._ways.iteritems():
            yield way


    def __getitem__(self, key):
        return self._ways[key]



class Relation(object):
    """ Represents an OSM Relation.

    Attributes:
        osm_id - The OSM ID of the relation.
        tags - Dictionary of tags, keyed by the tag's key.
        _members - list of tuples of the members of the relation. Each tuple
            contains (osm_element, role)
        _type - 'relation'
    """


    def __init__(self, osm_id):
        """ Initializes the relation.

        Inputs:
            osm_id - The OSM id of the relation

        Outputs:
            <nothing>
        """
        self.osm_id = osm_id
        self.tags = {}
        self.members = []


    def add_tag(self, key, value):
        """ Adds a tag to the relation.

        Inputs:
            key - The key of the tag to add.
            value - The value of the tag to add.

        Output:
            <nothing>
        """
        self.tags[key] = value


    def delete_tag(self, key):
        """ Deletes a tag from the relation.

        Inputs:
            Key - key of the tag to delete

        Output:
            <nothing>
        """
        del self.tags[key]


    def add_member(self, osm_element, role):
        """ Adds a member (a node, way or other relation) to the relation.

        Inputs:
            osm_id - the OSM element to be added as a member.
            role - The role within the relation the member is to play (e.g.
                'inner', 'outer', etc.)

        Output:
            <nothing>
        """
        self.members.append((osm_element, role))


    def write_xml(self, xml_out):
        """ Writes out the relation in XML format.

        Inputs:
            xml_out - file object which the xml will be written

        Outputs:
            <nothing>
        """
        xml_out.write('<relation id="{}" visible="true">\n'.format(self.osm_id))
        for member in self.members:
            xml_out.write('    <member ref="{}" type="{}" role="{}" />\n'
                          .format(member[0].osm_id, type(member[0]).__name__.lower(), member[1]))
        for key, value in self.tags.iteritems():
            xml_out.write('    <tag k="{}" v="{}" />\n'.format(key, value))
        xml_out.write('</relation>\n')



class Relations(object):
    """ Collection of OSM relations.

    Attributes:
        _relations = Dictionary, keyed by OSM ID, of the relations in the
            collection.
        _lowest_id = the lowest OSM ID of any relation in the collection. This
            is used to determine the ID of a new relation.
    """


    def __init__(self):
        """ Initializes the collection of relations.

        Inputs:
            <nothing>

        Outputs:
            <nothing>
        """
        self._relations = {}
        self._lowest_id = -1


    def add(self, relation):
        """ Adds an existing relation to the collection.

        Inputs:
            relation - An object of the Relation class defined in this module
                to be added to the collection.
        """
        self._relations[relation.osm_id] = relation
        if int(relation.osm_id) < self._lowest_id:
            self._lowest_id = int(relation.osm_id)


    def add_new(self):
        """ Creates an empty relation, assigns it an ID one less than the
        current lowest ID, adds it to the collection, and returns it.

        Inputs:
            <nothing>

        Output:
            The new relation
        """
        self._lowest_id -= 1
        new_relation = Relation(self._lowest_id)
        self.add(new_relation)
        return new_relation


    def write_xml(self, xml_out):
        """ Writes out the relations in order from highest to lowest OSM id in
        XML format.

        Inputs:
            xml_out - file object which the xml will be written

        Outputs:
            <nothing>
        """
        for key in sorted(self._relations, key=int, reverse=True):
            self._relations[key].write_xml(xml_out)


    def __iter__(self):
        for _, relation in self._relations.iteritems():
            yield relation


    def __getitem__(self, key):
        return self._relations[key]



class MakeBuildingRelations(object):
    """ Target object of the parser

    Attributes:
        bldgs - Dictionary, keyed by bldg_id, of building parts.
        nodes - Collection of all of the nodes in the dataset.
        ways - Collection of all of the ways in the dataset.
        relations - Collection of all of the relations in the dataset.
        part_level_tags - List of tags that should be exclusively applied to
            building parts.
        bldg_and_part_level_tags - List of tags that should be applied to both
            building parts and buildings.
        output_file_name - Name of file that output will be written to.
        bldg_id_tag - The OSM tag which will used to join the various building
            parts into a relation.
    """


    def __init__(self, output_file_name, bldg_id_tag):
        self.bldgs = {}
        self.nodes = Nodes()
        self.ways = Ways()
        self.relations = Relations()
        self.part_level_tags = ['height', 'type']
        self.bldg_and_part_level_tags = ['building']
        self.output_file_name = output_file_name
        self.bldg_id_tag = bldg_id_tag
        self.primary_osm_element = None


    def start(self, tag, attrib):
        """ Called for each opening XML tag

        Inputs:
            tag - The XML tag that was just started.
            attrib - Dictionary of XML attributes associated with the tag.

        Outputs:
            <nothing>
        """
        if tag == 'node':
            self.primary_osm_element = Node(attrib['id'], attrib['lat'], attrib['lon'])
        elif tag == 'way':
            self.primary_osm_element = Way(attrib['id'])
        elif tag == 'relation':
            self.primary_osm_element = Relation(attrib['id'])
        elif tag == 'tag':
            self.primary_osm_element.add_tag(attrib['k'], attrib['v'])
        elif tag == 'nd':
            self.primary_osm_element.add_node(self.nodes[attrib['ref']])
        elif tag == 'member':
            if attrib['type'] == 'node':
                element = self.nodes[attrib['ref']]
            elif attrib['type'] == 'way':
                element = self.ways[attrib['ref']]
            elif attrib['type'] == 'relation':
                element = self.relations[attrib['ref']]
            self.primary_osm_element.add_member(element, attrib['role'])


    def end(self, tag):
        """ Called for each closing XML tag

        Inputs:
            tag - String, the XML tag that was just closed.

        Output:
            <nothing>
        """
        if tag == 'node':
            self.nodes.add(self.primary_osm_element)
        elif tag == 'way':
            self.ways.add(self.primary_osm_element)
        elif tag == 'relation':
            self.relations.add(self.primary_osm_element)
        if tag in ('way', 'relation') and self.bldg_id_tag in self.primary_osm_element.tags:
            self.bldgs.setdefault(self.primary_osm_element.tags[self.bldg_id_tag], []) \
                .append(self.primary_osm_element)


    def data(self, data):
        """ Called when XML data is received, that is the text between the start
        and end tags.  In the OSM XML format there is no XML 'data', so there is
        nothing to do here.

        Inputs:
            data - The XML data.

        Output:
            <nothing>
        """
        pass


    def close(self):
        """ Called when all of the data in the XML file has been parsed.
        """
        # Clean up the building and building:part tags in the ways and relations
        for way in self.ways:
            if 'building' in way.tags and 'building:part' in way.tags:
                way.delete_tag('building:part')
            elif 'building' not in way.tags and 'building:part' in way.tags:
                way.add_tag('building', way.tags['building:part'].lower())
                way.delete_tag('building:part')
        for relation in self.relations:
            if 'building' in relation.tags and 'building:part' in relation.tags:
                relation.delete_tag('building:part')
            elif 'building' not in relation.tags and 'building:part' in relation.tags:
                relation.add_tag('building', relation.tags['building:part'].lower())
                relation.delete_tag('building:part')
        # Build the 'building' relations
        for bldg_id in self.bldgs:
            # Only make building relations if there is more than one part.
            if len(self.bldgs[bldg_id]) > 1:
                polygons = []
                bldg_relation = self.relations.add_new()
                bldg_relation.add_tag('type', 'building')
                for bldg_part in self.bldgs[bldg_id]:
                    if isinstance(bldg_part, Way):
                        polygons.append(self.way_to_polygon(bldg_part))
                    else:
                        polygons = polygons + self.relation_to_polygons(bldg_part)
                # Union the polygons representing all of the parts to get the outline
                outline = cascaded_union(polygons)
                if isinstance(outline, Polygon):
                    if not outline.interiors:
                        element = self._simple_polygon_to_way(outline)
                    else:
                        element = self._polygon_with_interior_to_relation(outline)
                elif isinstance(outline, MultiPolygon):
                    element = self.convert_multipolygon(outline)
                bldg_relation.add_member(element, 'outline')
                # Add tags to the outline
                for bldg_part in self.bldgs[bldg_id]:
                    tags_to_delete = []
                    for key, value in bldg_part.tags.iteritems():
                        if key not in self.part_level_tags:
                            element.add_tag(key, value)
                        if (key not in  self.part_level_tags
                                and key not in self.bldg_and_part_level_tags):
                            tags_to_delete.append(key)
                    for key in tags_to_delete:
                        bldg_part.delete_tag(key)
                    if 'building' in bldg_part.tags:
                        bldg_part.add_tag('building:part', bldg_part.tags['building'])
                        bldg_part.delete_tag('building')
                    bldg_relation.add_member(bldg_part, 'part')
        with open(self.output_file_name, 'w') as xml_out:
            xml_out.write('<?xml version="1.0"?>\n')
            xml_out.write('<osm version="0.6" upload="false" generator="uvmogr2osm">\n')
            self.nodes.write_xml(xml_out)
            self.ways.write_xml(xml_out)
            self.relations.write_xml(xml_out)
            xml_out.write('</osm>\n')


    def _points_to_way(self, points):
        """ Converts a list of points to a way.

        Inputs:
            points - a sequence of tuples containing a longitude and latitude

        Output:
            An instance of the Way class which is part of this module.
        """
        way = self.ways.add_new()
        for point in points:
            node = self.nodes.add_new_if_not_exist(str(point[1]), str(point[0]))
            way.add_node(node)
        return way


    def _simple_polygon_to_way(self, polygon):
        """ Converts a Shapely polygon with no holes (only a single outter ring
        and no inner rings) into a way.

        Inputs:
            polygon - a Shapely polygon

        Output:
            An instance of the Way class which is part of this module.
        """
        return self._points_to_way(list(polygon.exterior.coords))


    def _polygon_with_interior_to_relation(self, polygon):
        """ Converts a Shapely polygon with one or more holes (interior rings)
        into a Relation.

        Inputs:
            polygon - a Shapely polygon

        Output:
            An instance of the Relation class defined as part of this module.
        """
        relation = self.relations.add_new()
        relation.add_tag('type', 'multipolygon')
        self.add_polygon_to_relation(polygon, relation)
        return relation


    def add_polygon_to_relation(self, polygon, relation):
        """ Adds a shapely polygon to an OSM multipolygon relation.

        Inputs:
            polygon - The Shapely polygon to be added to the relation.
            relation - The multipolygon relation to which the above polygon is
                to be added.

        Output:
            <nothing>
        """
        way = self._points_to_way(list(polygon.exterior.coords))
        relation.add_member(way, 'outer')
        for linear_ring in polygon.interiors:
            way = self._points_to_way(list(linear_ring.coords))
            relation.add_member(way, 'inner')


    def convert_multipolygon(self, multi):
        """ Convert a Shapely to an OSM multipolygon relation.

        Inputs:
            multi - The Shapely multipolygon to be converted.

        Output:
            An OSM multipolygon relation representing the same geometry as the
                input Shapely multipolygon.
        """
        relation = self.relations.add_new()
        relation.add_tag('type', 'multipolygon')
        for polygon in multi:
            self.add_polygon_to_relation(polygon, relation)
        return relation


    @staticmethod
    def way_to_polygon(way):
        """ Convert an OSM way to a Shapely polygon.

        Inputs:
            way - The OSM way to be converted.

        Output:
            A Shapely polygon representing the same geometry as the input
                way.
        """
        points = []
        for node in way.nodes:
            points.append((float(node.lon), float(node.lat)))
        return Polygon(points)


    @staticmethod
    def relation_to_polygons(relation):
        """ Convert an OSM relation to a list of Shapely polygons.

        Inputs:
            relation - The OSM multipolygon relation to be converted

        Output:
            List of one or more Shapely polygons that resulted from converting
                the given OSM multipolygon relation.
        """
        lines = []
        for member in relation.members:
            way = member[0]
            points = []
            for node in way.nodes:
                points.append((float(node.lon), float(node.lat)))
            lines.append(tuple(points))
        return list(polygonize(lines))


def main():
    """ main funciton handles getting the command line parameters and starting
    the parsing.
    """

    # Parse command line arguments
    parser = argparse.ArgumentParser(prog='Make Building Relations',
                                     description='Makes OSM building relations ')
    parser.add_argument("--version", "-v", action="version",
                        version="%(prog)s " + __version__)
    parser.add_argument("input_osm", metavar="input.osm",
                        help="Input OSM data in xml format")
    parser.add_argument("output_osm", metavar="output.osm",
                        help="File to which to write the output")
    parser.add_argument("bldg_id_tag", metavar="bldg_id_tag",
                        help="OSM tag key to be used to join together the various building parts"
                        + " into a relation")
    args = parser.parse_args(sys.argv[1:])
    input_osm = args.input_osm
    parser = XMLParser(target=MakeBuildingRelations(args.output_osm, args.bldg_id_tag))
    with open(input_osm, 'r') as osm_in:
        parser.feed(osm_in.read())
    parser.close()


if __name__ == '__main__':
    main()
