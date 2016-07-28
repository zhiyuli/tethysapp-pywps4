from django.shortcuts import render
from django.contrib.auth.decorators import login_required


from processes.sleep import Sleep
from processes.ultimate_question import UltimateQuestion
from processes.centroids import Centroids
from processes.sayhello import SayHello
from processes.feature_count import FeatureCount
from processes.buffer import Buffer
from processes.area import Area
from processes.bboxinout import Box
from pywps.app.Service import Service
from werkzeug.wrappers import Request as werkzeug_Request

import os
import uuid
from pywps.app.WPSRequest import WPSRequest
from pywps.dblog import log_request, update_response
from django.http import HttpResponse

@login_required()
def home(request):



    """
    Controller for the app home page.
    """
    context = {}

    return render(request, 'pywps4/home.html', context)


#http://127.0.0.1:8000/apps/pywps4/wps/?service=wps&request=GetCapabilities
#http://127.0.0.1:8000/apps/pywps4/wps/?Request=DescribeProcess&Service=WPS&Version=1.0.0&Identifier=area
def wps(request):

    processes = [
        FeatureCount(),
        SayHello(),
        Centroids(),
        UltimateQuestion(),
        Sleep(),
        Buffer(),
        Area(),
        Box()
    ]
    service = Service(processes=processes)
    http_request = werkzeug_Request(request.environ)
    print type(http_request)



    request_uuid = uuid.uuid1()
    response = None
    environ_cfg = http_request.environ.get('PYWPS_CFG')
    # if not 'PYWPS_CFG' in os.environ and environ_cfg:
    #     # LOGGER.debug('Setting PYWPS_CFG to %s', environ_cfg)
    #     os.environ['PYWPS_CFG'] = environ_cfg

    # try:
    wps_request = WPSRequest(http_request)
    # LOGGER.info('Request: %s', wps_request.operation)
    if wps_request.operation in ['getcapabilities',
                                 'describeprocess',
                                 'execute']:
        # log_request(request_uuid, wps_request)
        response = None
        if wps_request.operation == 'getcapabilities':
            response = service.get_capabilities()

        elif wps_request.operation == 'describeprocess':
            response = service.describe(wps_request.identifiers)

        elif wps_request.operation == 'execute':
            response = service.execute(
                wps_request.identifier,
                wps_request,
                request_uuid
            )
        update_response(request_uuid, response, close=True)
        # return response
    else:
        update_response(request_uuid, response, close=True)
        raise RuntimeError("Unknown operation %r"
                           % wps_request.operation)

    print response.get_data()
    # except HTTPException as e:
    #     # transform HTTPException to OWS NoApplicableCode exception
    #     if not isinstance(e, NoApplicableCode):
    #         e = NoApplicableCode(e.description, code=e.code)
    #
    #     class FakeResponse:
    #         message = e.locator
    #         status = e.code
    #         status_percentage = 100
    #     update_response(request_uuid, FakeResponse, close=True)
    #     return e

    return HttpResponse(response.get_data(), content_type='application/xhtml+xml')
    #