###############################################################################
#
# Copyright (C) 2014-2016 PyWPS Development Team, represented by
# PyWPS Project Steering Committee
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
#
###############################################################################

import logging
import os
import sys
import traceback
import json
import shutil
import tempfile

from pywps import WPS, OWS, E, dblog
from pywps.app.WPSResponse import WPSResponse
from pywps.app.WPSRequest import WPSRequest
import pywps.configuration as config
from pywps._compat import PY2
from pywps.exceptions import StorageNotSupported, OperationNotSupported, \
    ServerBusy, NoApplicableCode


LOGGER = logging.getLogger("PYWPS")

class Process(object):
    """
    :param handler: A callable that gets invoked for each incoming
                    request. It should accept a single
                    :class:`~WPSRequest` argument and return a
                    :class:`~WPSResponse` object.
    :param identifier: Name of this process.
    :param inputs: List of inputs accepted by this process. They
                   should be :class:`~LiteralInput` and :class:`~ComplexInput`
                   and :class:`~BoundingBoxInput`
                   objects.
    :param outputs: List of outputs returned by this process. They
                   should be :class:`~LiteralOutput` and :class:`~ComplexOutput`
                   and :class:`~BoundingBoxOutput`
                   objects.
    """

    def __init__(self, handler, identifier, title, abstract='', profile=[], metadata=[], inputs=[],
                 outputs=[], version='None', store_supported=False, status_supported=False, grass_location=None):
        self.identifier = identifier
        self.handler = handler
        self.title = title
        self.abstract = abstract
        self.metadata = metadata
        self.profile = profile
        self.version = version
        self.inputs = inputs
        self.outputs = outputs
        self.uuid = None
        self.status_location = ''
        self.status_url = ''
        self.workdir = None
        self._grass_mapset = None
        self.grass_location = grass_location


        if store_supported:
            self.store_supported = 'true'
        else:
            self.store_supported = 'false'

        if status_supported:
            self.status_supported = 'true'
        else:
            self.status_supported = 'false'



    def capabilities_xml(self):
        doc = WPS.Process(
            OWS.Identifier(self.identifier),
            OWS.Title(self.title)
        )
        if self.abstract:
            doc.append(OWS.Abstract(self.abstract))
        # TODO: See Table 32 Metadata in OGC 06-121r3
        #for m in self.metadata:
        #    doc.append(OWS.Metadata(m))
        if self.profile:
            doc.append(OWS.Profile(self.profile))
        if self.version != 'None':
            doc.attrib['{http://www.opengis.net/wps/1.0.0}processVersion'] = self.version
        else:
            doc.attrib['{http://www.opengis.net/wps/1.0.0}processVersion'] = 'undefined'

        return doc

    def describe_xml(self):
        input_elements = [i.describe_xml() for i in self.inputs]
        output_elements = [i.describe_xml() for i in self.outputs]

        doc = E.ProcessDescription(
            OWS.Identifier(self.identifier),
            OWS.Title(self.title)
        )
        doc.attrib['{http://www.opengis.net/wps/1.0.0}processVersion'] = self.version

        if self.store_supported == 'true':
            doc.attrib['storeSupported'] = self.store_supported

        if self.status_supported == 'true':
            doc.attrib['statusSupported'] = self.status_supported

        if self.abstract:
            doc.append(OWS.Abstract(self.abstract))

        for m in self.metadata:
            doc.append(OWS.Metadata({'{http://www.w3.org/1999/xlink}title': m}))

        for p in self.profile:
            doc.append(WPS.Profile(p))

        if input_elements:
            doc.append(E.DataInputs(*input_elements))

        doc.append(E.ProcessOutputs(*output_elements))

        return doc

    def execute(self, wps_request, uuid):
        self._set_uuid(uuid)
        async = False
        wps_response = WPSResponse(self, wps_request, self.uuid)

        LOGGER.debug('Check if status storage and updating are supported by this process')
        if wps_request.store_execute == 'true':
            if self.store_supported != 'true':
                raise StorageNotSupported('Process does not support the storing of the execute response')


            if wps_request.status == 'true':
                if self.status_supported != 'true':
                    raise OperationNotSupported('Process does not support the updating of status')

                wps_response.status = WPSResponse.STORE_AND_UPDATE_STATUS
                async = True
            else:
                wps_response.status = WPSResponse.STORE_STATUS

        LOGGER.debug('Check if updating of status is not required then no need to spawn a process')

        wps_response = self._execute_process(async, wps_request, wps_response)

        return wps_response

    def _set_uuid(self, uuid):
        """Set uuid and status ocation apth and url
        """

        self.uuid = uuid

        file_path = config.get_config_value('server', 'outputpath')

        file_url = config.get_config_value('server', 'outputurl')

        self.status_location = os.path.join(file_path, str(self.uuid)) + '.xml'
        self.status_url = os.path.join(file_url, str(self.uuid)) + '.xml'

    def _execute_process(self, async, wps_request, wps_response):
        """Uses :module:`multiprocessing` module for sending process to
        background BUT first, check for maxprocesses configuration value

        :param async: run in asynchronous mode
        :return: wps_response or None
        """

        maxparalel = int(config.get_config_value('server', 'parallelprocesses'))
        running = len(dblog.get_running())
        stored = len(dblog.get_stored())

        # async
        if async:

            # run immedietly
            if running < maxparalel:
                self._run_async(wps_request, wps_response)

            # try to store for later usage
            else:
                wps_response = self._store_process(stored,
                                                   wps_request, wps_response)

        # not async
        else:
            if running < maxparalel:
                wps_response = self._run_process(wps_request, wps_response)
            else:
                raise ServerBusy('Maximum number of paralel running processes reached. Please try later.')

        return wps_response

    def _run_async(self, wps_request, wps_response):
        import multiprocessing
        process = multiprocessing.Process(
            target=self._run_process,
            args=(wps_request, wps_response)
        )
        process.start()


    def _store_process(self, stored, wps_request, wps_response):
        """Try to store given requests
        """

        maxprocesses = int(config.get_config_value('server', 'maxprocesses'))

        if stored < maxprocesses:
            dblog.store_process(self.uuid, wps_request)
        else:
            raise ServerBusy('Maximum number of parallel running processes reached. Please try later.')

        return wps_response

    def _run_process(self, wps_request, wps_response):
        try:
            self._set_grass()
            wps_response = self.handler(wps_request, wps_response)

            # if status not yet set to 100% then do it after execution was successful
            if (not wps_response.status_percentage) or (wps_response.status_percentage != 100):
                LOGGER.debug('Updating process status to 100% if everything went correctly')
                wps_response.update_status('PyWPS Process finished', 100, wps_response.DONE_STATUS)
        except Exception as e:
            traceback.print_exc()
            LOGGER.debug('Retrieving file and line number where exception occurred')
            exc_type, exc_obj, exc_tb = sys.exc_info()
            found = False
            while not found:
                # search for the _handler method
                m_name = exc_tb.tb_frame.f_code.co_name
                if m_name == '_handler':
                    found = True
                else:
                    if exc_tb.tb_next is not None:
                        exc_tb = exc_tb.tb_next
                    else:
                        # if not found then take the first
                        exc_tb = sys.exc_info()[2]
                        break
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            method_name = exc_tb.tb_frame.f_code.co_name

            # update the process status to display process failed
            msg = 'Process error: %s.%s Line %i %s' % (fname, method_name, exc_tb.tb_lineno, e)
            LOGGER.error(msg)

            if not wps_response:
                raise NoApplicableCode('Response is empty. Make sure the _handler method is returning a valid object.')
            else:
                wps_response.update_status(msg, -1)

        # tr
        stored_requests = dblog.get_first_stored()
        if len(stored_requests) > 0:
            (uuid, request_json) = stored_requests[0]
            new_wps_request = WPSRequest()
            new_wps_request.json = json.loads(request_json)
            new_wps_response = WPSResponse(self, new_wps_request, uuid)
            new_wps_response.status = WPSResponse.STORE_AND_UPDATE_STATUS
            self._set_uuid(uuid)
            self._run_async(new_wps_request, new_wps_response)
            dblog.remove_stored(uuid)


        return wps_response

    def clean(self):
        """Clean the process working dir and other temporary files
        """
        LOGGER.info("Removing temporary working directory: %s" % self.workdir)
        if os.path.isdir(self.workdir):
            shutil.rmtree(self.workdir)
        if self._grass_mapset and os.path.isdir(self._grass_mapset):
            LOGGER.info("Removing temporary GRASS GIS mapset: %s" % self._grass_mapset)
            shutil.rmtree(self._grass_mapset)

    def set_workdir(self, workdir):
        """Set working dir for all inputs and outputs

        this is the directory, where all the data are being stored to
        """

        self.workdir = workdir
        for inpt in self.inputs:
            inpt.workdir = workdir

        for outpt in self.outputs:
            outpt.workdir = workdir

    def _set_grass(self):
        """Handle given grass_location parameter of the constructor

        location is either directory name or 'epsg:1234' form

        in the first case, new temporary mapset within the location will be
        created

        in the second case, location will be created in self.workdir

        the mapset should be deleted automatically using self.clean() method
        """

        if not PY2:
            LOGGER.warning('Seems PyWPS is running in Python-3 ' +
                'environment, but GRASS GIS supports Python-2 only')
            return

        if self.grass_location:

            from grass.script import core as grass
            import grass.script.setup as gsetup

            dbase = ''
            location = ''

            # HOME needs to be set - and that is usually not the case for httpd
            # server
            os.environ['HOME'] =  self.workdir

            # GISRC envvariable needs to be set
            gisrc = open(os.path.join(self.workdir, 'GISRC'), 'w')
            gisrc.write("GISDBASE: %s\n" % self.workdir)
            gisrc.write("GUI: txt\n")
            gisrc.close()
            os.environ['GISRC'] = gisrc.name

            # create new location from epsg code
            if self.grass_location.lower().startswith('epsg:'):
                epsg = self.grass_location.lower().replace('epsg:', '')
                dbase = self.workdir
                os.environ['GISDBASE'] =  self.workdir
                location = 'pywps_location'
                grass.run_command('g.gisenv', set="GISDBASE=%s" % dbase)
                grass.run_command('g.proj', flags="t", location=location, epsg=epsg)
                LOGGER.debug('GRASS location based on EPSG code created')

            # create temporary mapset within existing location
            elif os.path.isdir(self.grass_location):
                LOGGER.debug('Temporary mapset will be created')
                dbase = os.path.dirname(self.grass_location)
                location = os.path.basename(self.grass_location)
                grass.run_command('g.gisenv', set="GISDBASE=%s" % dbase)

            else:
                raise NoApplicableCode(
                    'Location does exists or does not seem to be in "EPSG:XXXX" form nor is it existing directory: %s' % location)

            # copy projection files from PERMAMENT mapset to temporary mapset
            mapset_name = tempfile.mkdtemp(prefix='pywps_', dir=os.path.join(dbase, location))
            shutil.copy(os.path.join(dbase, location, 'PERMANENT',
                'DEFAULT_WIND'), os.path.join(mapset_name, 'WIND'))
            shutil.copy(os.path.join(dbase, location, 'PERMANENT',
                'PROJ_EPSG'), os.path.join(mapset_name, 'PROJ_EPSG'))
            shutil.copy(os.path.join(dbase, location, 'PERMANENT',
                'PROJ_INFO'), os.path.join(mapset_name, 'PROJ_INFO'))
            shutil.copy(os.path.join(dbase, location, 'PERMANENT',
                'PROJ_UNITS'), os.path.join(mapset_name, 'PROJ_UNITS'))

            # set _grass_mapset attribute - will be deleted once handler ends
            self._grass_mapset = mapset_name

            # final initialization
            LOGGER.debug('GRASS Mapset set to %s' % mapset_name)
            grass.run_command('g.gisenv', set="LOCATION_NAME=%s" % location)
            grass.run_command('g.gisenv', set="MAPSET=%s" % os.path.basename(mapset_name))

            LOGGER.debug(
                'GRASS environment initialised with GISRC {}, GISBASE {}, GISDBASE {}, LOCATION {}, MAPSET {}'.format(
                os.environ.get('GISRC'), os.environ.get('GISBASE'),
                dbase, location, os.path.basename(mapset_name)))
