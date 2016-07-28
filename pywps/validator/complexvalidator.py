"""Validator classes are used for ComplexInputs, to validate the content
"""
# Author:    Jachym Cepicky
#            
# License:
#
# Web Processing Service implementation
# Copyright (C) 2014-2015 PyWPS Development Team, represented by Jachym Cepicky
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

import logging

from pywps.validator.mode import MODE
from pywps.inout.formats.lists import FORMATS
import mimetypes
import os

LOGGER = logging.getLogger('PYWPS')

def validategml(data_input, mode):
    """GML validation example

    >>> import StringIO
    >>> class FakeInput(object):
    ...     gml = open('point.gml','w')
    ...     gml.write('''<?xml version="1.0" ?>
    ...     <gml:featureMember xmlns:gml="http://www.opengis.net/gml" xsi:schemaLocation="http://www.opengis.net/gml http://schemas.opengis.net/gml/2.1.2/feature.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><feature:feature xmlns:feature="http://example.com/feature"><feature:geometry><gml:Point><gml:coordinates decimal="." cs=", " ts=" ">-1, 1</gml:coordinates></gml:Point></feature:geometry></feature:feature></gml:featureMember>''')
    ...     gml.close()
    ...     file = 'point.gml'
    >>> class fake_data_format(object):
    ...     mimetype = 'application/gml+xml'
    >>> fake_input = FakeInput()
    >>> fake_input.data_format = fake_data_format()
    >>> validategml(fake_input, MODE.SIMPLE)
    True
    """

    LOGGER.info('validating GML; Mode: %s', mode)
    passed = False

    if mode >= MODE.NONE:
        passed = True
    import sys

    if mode >= MODE.SIMPLE:

        name = data_input.file
        (mtype, encoding) = mimetypes.guess_type(name, strict=False)
        passed = data_input.data_format.mime_type in {mtype, FORMATS.GML.mime_type}

    if mode >= MODE.STRICT:

        from pywps.dependencies import ogr
        data_source = ogr.Open(data_input.file)
        if data_source:
            passed = (data_source.GetDriver().GetName() == "GML")
        else:
            passed = False

    if mode >= MODE.VERYSTRICT:

        from lxml import etree

        from pywps._compat import PY2
        if PY2:
            from urllib2 import urlopen
        else:
            from urllib.request import urlopen

        try:
            schema_url = data_input.data_format.schema
            gmlschema_doc = etree.parse(urlopen(schema_url))
            gmlschema = etree.XMLSchema(gmlschema_doc)
            passed = gmlschema.validate(etree.parse(data_input.stream))
        except Exception as e:
            passed = False

    return passed

def validategeojson(data_input, mode):
    """GeoJSON validation example

    >>> import StringIO
    >>> class FakeInput(object):
    ...     json = open('point.geojson','w')
    ...     json.write('''{"type":"Feature", "properties":{}, "geometry":{"type":"Point", "coordinates":[8.5781228542328, 22.87500500679]}, "crs":{"type":"name", "properties":{"name":"urn:ogc:def:crs:OGC:1.3:CRS84"}}}''')
    ...     json.close()
    ...     file = 'point.geojson'
    >>> class fake_data_format(object):
    ...     mimetype = 'application/geojson'
    >>> fake_input = FakeInput()
    >>> fake_input.data_format = fake_data_format()
    >>> validategeojson(fake_input, MODE.SIMPLE)
    True
    """

    LOGGER.info('validating GeoJSON; Mode: %s', mode)
    passed = False

    if mode >= MODE.NONE:
        passed = True

    if mode >= MODE.SIMPLE:

        name = data_input.file
        (mtype, encoding) = mimetypes.guess_type(name, strict=False)
        passed = data_input.data_format.mime_type in {mtype, FORMATS.GEOJSON.mime_type}

    if mode >= MODE.STRICT:

        from pywps.dependencies import ogr
        data_source = ogr.Open(data_input.file)
        if data_source:
            passed = (data_source.GetDriver().GetName() == "GeoJSON")
        else:
            passed = False

    if mode >= MODE.VERYSTRICT:

        import jsonschema
        import json

        # this code comes from
        # https://github.com/om-henners/GeoJSON_Validation/blob/master/geojsonvalidation/geojson_validation.py
        schema_home = os.path.join(_get_schemas_home(), "geojson")
        base_schema = os.path.join(schema_home, "geojson.json")

        with open(base_schema) as fh:
            geojson_base = json.load(fh)

        with open(os.path.join(schema_home, "crs.json")) as fh:
            crs_json = json.load(fh)

        with open(os.path.join(schema_home, "bbox.json")) as fh:
            bbox_json = json.load(fh)

        with open(os.path.join(schema_home, "geometry.json")) as fh:
            geometry_json = json.load(fh)

        cached_json = {
            "http://json-schema.org/geojson/crs.json": crs_json,
            "http://json-schema.org/geojson/bbox.json": bbox_json,
            "http://json-schema.org/geojson/geometry.json": geometry_json
        }

        resolver = jsonschema.RefResolver(
            "http://json-schema.org/geojson/geojson.json",
            geojson_base, store=cached_json)

        validator = jsonschema.Draft4Validator(geojson_base, resolver=resolver)
        try:
            validator.validate(json.loads(data_input.stream.read()))
            passed = True
        except jsonschema.ValidationError:
            passed = False

    return passed

def validateshapefile(data_input, mode):
    """ESRI Shapefile validation example

    """

    LOGGER.info('validating Shapefile; Mode: %s', mode)
    passed = False

    if mode >= MODE.NONE:
        passed = True

    if mode >= MODE.SIMPLE:

        name = data_input.file
        (mtype, encoding) = mimetypes.guess_type(name, strict=False)
        passed = data_input.data_format.mime_type in {mtype, FORMATS.SHP.mime_type}

    if mode >= MODE.STRICT:

        from pywps.dependencies import ogr

        import zipfile
        z = zipfile.ZipFile(data_input.file)
        shape_name = None
        for name in z.namelist():
            z.extract(name, data_input.tempdir)
            if os.path.splitext(name)[1].lower() == '.shp':
                shape_name = name

        if shape_name:
            data_source = ogr.Open(os.path.join(data_input.tempdir, shape_name))

        if data_source:
            passed = (data_source.GetDriver().GetName() == "ESRI Shapefile")
        else:
            passed = False

    return passed

def validategeotiff(data_input, mode):
    """GeoTIFF validation example
    """

    LOGGER.info('Validating Shapefile; Mode: %s', mode)
    passed = False

    if mode >= MODE.NONE:
        passed = True

    if mode >= MODE.SIMPLE:

        name = data_input.file
        (mtype, encoding) = mimetypes.guess_type(name, strict=False)
        passed = data_input.data_format.mime_type in {mtype, FORMATS.GEOTIFF.mime_type}

    if mode >= MODE.STRICT:

        from pywps.dependencies import gdal
        data_source = gdal.Open(data_input.file)
        if data_source:
            passed = (data_source.GetDriver().ShortName == "GTiff")
        else:
            passed = False

    return passed

def _get_schemas_home():
    """Get path to schemas directory
    """
    schema_dir = os.path.join(
        os.path.abspath(
            os.path.dirname(__file__)
        ),
        os.path.pardir,
        "schemas")
    LOGGER.debug('Schemas directory: %s', schema_dir)
    return schema_dir


if __name__ == "__main__":
    import doctest

    import os
    from pywps.wpsserver import temp_dir

    with temp_dir() as tmp:
        os.chdir(tmp)
        doctest.testmod()
