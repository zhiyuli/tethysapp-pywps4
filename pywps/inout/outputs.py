from pywps._compat import text_type
from pywps import E, WPS, OWS, OGCTYPE, NAMESPACES
from pywps.inout import basic
from pywps.inout.storage import FileStorage
from pywps.inout.formats import Format
from pywps.validator.mode import MODE
import lxml.etree as etree


class BoundingBoxOutput(basic.BBoxInput):
    """
    :param identifier: The name of this input.
    """

    def __init__(self, identifier, title, crss, abstract='',
                 dimensions=2, metadata=None, min_occurs='1',
                 max_occurs='1', as_reference=False,
                 mode=MODE.NONE):
        if metadata is None:
            metadata = []
        basic.BBoxInput.__init__(self, identifier, title=title,
                                 abstract=abstract, crss=crss,
                                 dimensions=dimensions, mode=mode)

        self.metadata = metadata
        self.min_occurs = min_occurs
        self.max_occurs = max_occurs
        self.as_reference = as_reference

    def describe_xml(self):
        doc = E.Output(
            OWS.Identifier(self.identifier),
            OWS.Title(self.title)
        )

        if self.abstract:
            doc.append(OWS.Abstract(self.abstract))

        if self.metadata:
            doc.append(OWS.Metadata(*self.metadata))

        bbox_data_doc = E.BoundingBoxOutput()
        doc.append(bbox_data_doc)

        default_doc = E.Default()
        default_doc.append(E.CRS(self.crss[0]))

        supported_doc = E.Supported()
        for c in self.crss:
            supported_doc.append(E.CRS(c))

        bbox_data_doc.append(default_doc)
        bbox_data_doc.append(supported_doc)

        return doc

    def execute_xml(self):
        doc = E.Output(
            OWS.Identifier(self.identifier),
            OWS.Title(self.title)
        )

        if self.abstract:
            doc.append(OWS.Abstract(self.abstract))

        bbox_data_doc = OWS.BoundingBox()

        bbox_data_doc.attrib['crs'] = self.crs
        bbox_data_doc.attrib['dimensions'] = str(self.dimensions)

        bbox_data_doc.append(OWS.LowerCorner('{0[0]} {0[1]}'.format(self.data)))
        bbox_data_doc.append(OWS.UpperCorner('{0[2]} {0[3]}'.format(self.data)))

        doc.append(bbox_data_doc)

        return doc


class ComplexOutput(basic.ComplexOutput):
    """
    :param identifier: The name of this output.
    :param title: Readable form of the output name.
    :param supported_formats: List of supported
            output formats for this output.
            Should be list of :class:`~Format` object.
            The first format in the list will be used as the default.
    :param abstract: Description of the output
    """

    def __init__(self, identifier, title,  supported_formats=None,
                 abstract='', metadata=None, mode=MODE.NONE):
        if metadata is None:
            metadata = []

        basic.ComplexOutput.__init__(self, identifier, title=title,
                                     abstract=abstract,
                                     supported_formats=supported_formats,
                                     mode=mode)
        self.metadata = metadata
        self.as_reference = False

        self.storage = None

    def describe_xml(self):
        """Generate DescribeProcess element
        """
        default_format_el = self.supported_formats[0].describe_xml()
        supported_format_elements = [f.describe_xml() for f in self.supported_formats]

        doc = E.Output(
            OWS.Identifier(self.identifier),
            OWS.Title(self.title)
        )

        if self.abstract:
            doc.append(OWS.Abstract(self.abstract))

        for m in self.metadata:
            doc.append(OWS.Metadata(*self.metadata))

        doc.append(
            E.ComplexOutput(
                E.Default(default_format_el),
                E.Supported(*supported_format_elements)
            )
        )

        return doc

    def execute_xml(self):
        """Render Execute response XML node

        :return: node
        :rtype: ElementMaker
        """

        self.identifier

        node = None
        if self.as_reference:
            node = self._execute_xml_reference()
        else:
            node = self._execute_xml_data()

        doc = WPS.Output(
            OWS.Identifier(self.identifier),
            OWS.Title(self.title)
        )
        if self.abstract:
            doc.append(OWS.Abstract(self.abstract))
        doc.append(node)

        return doc

    def _execute_xml_reference(self):
        """Return Reference node
        """
        doc = WPS.Reference()

        # get_url will create the file and return the url for it
        self.storage = FileStorage()
        doc.attrib['{http://www.w3.org/1999/xlink}href'] = self.get_url()

        if self.data_format:
            if self.data_format.mime_type:
                doc.attrib['mimeType'] = self.data_format.mime_type
            if self.data_format.encoding:
                doc.attrib['encoding'] = self.data_format.encoding
            if self.data_format.schema:
                doc.attrib['schema'] = self.data_format.schema
        return doc

    def _execute_xml_data(self):
        """Return Data node
        """
        doc = WPS.Data()


        if self.data is None:
            complex_doc = WPS.ComplexData()
        else:
            complex_doc = WPS.ComplexData()
            try:
                data_doc = etree.parse(self.file)
                complex_doc.append(data_doc.getroot())
            except:
                complex_doc.text = etree.CDATA(self.base64)

        if self.data_format:
            if self.data_format.mime_type:
                complex_doc.attrib['mimeType'] = self.data_format.mime_type
            if self.data_format.encoding:
                complex_doc.attrib['encoding'] = self.data_format.encoding
            if self.data_format.schema:
                complex_doc.attrib['schema'] = self.data_format.schema
        doc.append(complex_doc)
        return doc


class LiteralOutput(basic.LiteralOutput):
    """
    :param identifier: The name of this output.
    :param data_type: Type of literal input (e.g. `string`, `float`...).
    :param value: Resulting value
            Should be :class:`~String` object.
    """

    def __init__(self, identifier, title, data_type='string', abstract='',
            metadata=[], uoms=[], mode=MODE.SIMPLE):
        if metadata is None:
            metadata = []
        if uoms is None:
            uoms = []
        basic.LiteralOutput.__init__(self, identifier, title=title,
                data_type=data_type, uoms=uoms, mode=mode)
        self.abstract = abstract
        self.metadata = metadata

    def describe_xml(self):
        doc = E.Output(
            OWS.Identifier(self.identifier),
            OWS.Title(self.title)
        )

        if self.abstract:
            doc.append(OWS.Abstract(self.abstract))

        for m in self.metadata:
            doc.append(OWS.Metadata(m))

        literal_data_doc = E.LiteralOutput()

        if self.data_type:
            data_type = OWS.DataType(self.data_type)
            data_type.attrib['{%s}reference' % NAMESPACES['ows']] = OGCTYPE[self.data_type]
            literal_data_doc.append(data_type)

        if self.uoms:
            default_uom_element = self.uom.describe_xml()
            supported_uom_elements = [u.describe_xml() for u in self.uoms]

            literal_data_doc.append(
                E.UOMs(
                    E.Default(default_uom_element),
                    E.Supported(*supported_uom_elements)
                )
            )

        doc.append(literal_data_doc)

        return doc

    def execute_xml_lineage(self):
        doc = WPS.Output(
            OWS.Identifier(self.identifier),
            OWS.Title(self.title)
        )

        if self.abstract:
            doc.append(OWS.Abstract(self.abstract))

        return doc


    def execute_xml(self):
        doc = WPS.Output(
            OWS.Identifier(self.identifier),
            OWS.Title(self.title)
        )

        if self.abstract:
            doc.append(OWS.Abstract(self.abstract))

        data_doc = WPS.Data()

        literal_data_doc = WPS.LiteralData(text_type(self.data))
        literal_data_doc.attrib['dataType'] = OGCTYPE[self.data_type]
        if self.uom:
            literal_data_doc.attrib['uom'] = self.uom.execute_attribute()
        data_doc.append(literal_data_doc)

        doc.append(data_doc)

        return doc
