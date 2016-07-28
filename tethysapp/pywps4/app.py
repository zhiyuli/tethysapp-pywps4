from tethys_sdk.base import TethysAppBase, url_map_maker


class TethysappPywps(TethysAppBase):
    """
    Tethys app class for tethysapp pywps.
    """

    name = 'tethysapp pywps'
    index = 'pywps4:home'
    icon = 'pywps4/images/icon.gif'
    package = 'pywps4'
    root_url = 'pywps4'
    color = '#2ecc71'
    description = ''
    tags = ''
    enable_feedback = False
    feedback_emails = []

        
    def url_maps(self):
        """
        Add controllers
        """
        UrlMap = url_map_maker(self.root_url)

        url_maps = (UrlMap(name='home',
                           url='pywps4',
                           controller='pywps4.controllers.home'),
                    UrlMap(name='wps',
                           url='pywps4/wps',
                           controller='pywps4.controllers.wps'),
        )

        return url_maps