import json
import base64
import urllib2
import socket
import os
import re
import sys
import xbmc, xbmcaddon, xbmcgui, xbmcplugin

# Constants

ADDON = xbmcaddon.Addon()

STRING = 0
BOOL = 1
NUM = 2

__path__ = xbmc.translatePath(ADDON.getAddonInfo('path'))
__LS__ = ADDON.getLocalizedString

FALLBACK = 'image://%s' % (os.path.join(__path__, 'resources', 'icons', 'fallback.png/'))


def get_media_symbol(mediatype):
    media = {'idle': 'power.png', 'audio': 'music.png', 'channel': 'tv.png', 'video': 'movie.png',
             'movie': 'movie.png', 'episode': 'video.png', 'offline': 'offline.png'}
    try:
        return os.path.join(__path__, 'resources', 'icons', media[mediatype])
    except (TypeError, KeyError):
        writeLog('Could not get icon for %s' % mediatype, xbmc.LOGERROR)
        return os.path.join(__path__, 'resources', 'icons', media['offline'])


def strToBool(par):
    return True if par.upper() == 'TRUE' else False


def unquote(image_url):
    return urllib2.unquote(image_url.split('://', 1)[1][:-1])

def writeLog(message, level=xbmc.LOGDEBUG):
    xbmc.log('[%s %s]: %s' % (ADDON.getAddonInfo('id'),
                              ADDON.getAddonInfo('version'), message.encode('utf-8')), level)


def getAddonSetting(setting, sType=STRING, multiplicator=1):
    if sType == BOOL:
        return strToBool(ADDON.getSetting(setting))
    elif sType == NUM:
        try:
            return int(re.match('\d+', ADDON.getSetting(setting)).group()) * multiplicator
        except AttributeError:
            writeLog('Could not read setting type NUM: %s' % setting, xbmc.LOGERROR)
            return 0
    else:
        return ADDON.getSetting(setting)


class fetchXBMC(object):

    def __init__(self, host, port=8080, path='/jsonrpc', username=None, passwd=None, query=None):
        self.host = host
        self.port = port
        self.path = path
        self.username = username
        self.passwd = passwd
        self.query = query

        self.m_item = {'host': self.host,
                       'label': 'idle',
                       'thumb': unquote(FALLBACK),
                       'label2': __LS__(30030),
                       'symbol': get_media_symbol('idle')
                       }

    def jsonrpc(self):

        data = None
        querystring = {"jsonrpc": "2.0", "id": 1}

        if self.query is not None:
            querystring.update(self.query)
            data = json.dumps(querystring)

        result = None
        try:
            request = urllib2.Request('http://%s:%s%s' % (self.host, self.port, self.path), data=data)
            request.add_header('Content-Type', 'application/json-rpc; charset=utf-8')

            if self.passwd is not None:
                b64 = base64.standard_b64encode('%s:%s' % (self.username, self.passwd))
                request.add_header('Authorization', 'Basic %s' % (b64))

            response = urllib2.urlopen(request, timeout=3)
            result = json.loads(response.read().strip()).get('result', None)
            response.close()

        except (urllib2.URLError, socket.timeout), e:
            writeLog('%s: Error raised: %s' % (self.host, getattr(e, 'reason', getattr(e, 'message', None))), xbmc.LOGERROR)

        return result

    def collectProperties(self):
        result = device.jsonrpc()
        if result is not None:

            # collect media infos

            symbol = result.get('item', '')['art']
            thumb = unquote(symbol.get('tvshow.fanart',
                            symbol.get('thumb', symbol.get('fanart',
                            symbol.get('poster', FALLBACK)))))

            self.m_item.update({'thumb': thumb})
            self.m_item.update({'label': result.get('item')['type']})
            self.m_item.update({'symbol': get_media_symbol(result.get('item')['type'])})
            self.m_item.update({'label2': result.get('item')['label']})

if __name__ == '__main__':

    args = sys.argv
    handle = None

    if len(args) > 1:

        if args[0][0:6] == 'plugin':
            writeLog('calling module as plugin source')
            handle = int(args[1])
            args.pop(0)
            args[1] = args[1][1:]
    
    hosts = 0
    for host in range(1, 7, 1):
        if getAddonSetting('host_%s_enabled' % host, sType=BOOL): hosts += 1
    writeLog('%s hosts for monitoring enabled' % hosts)

    if hosts > 0:
        for host in range(1, 7, 1):
            if getAddonSetting('host_%s_enabled' % host, sType=BOOL):

                host_name = getAddonSetting('host_%s_name' % host)
                host_port = getAddonSetting('host_%s_port' % host)
                host_user = getAddonSetting('host_%s_user' % host)
                host_pass = getAddonSetting('host_%s_passwd' % host)

                device = fetchXBMC(host_name, port=host_port, username=host_user, passwd=host_pass)
                device.query = {'method': 'Player.GetActivePlayers'}

                id = device.jsonrpc()
                if id is not None:
                    if len(id) > 0:
                        device.query = {'method': 'Player.GetItem',
                                        'params': {'playerid': id[0].get('playerid', None),
                                                   'properties': ['art']}}
                        device.collectProperties()
                        writeLog('%s: %s is playing' % (device.m_item['host'], device.m_item['label2']))
                        writeLog(str(device.m_item))
                    else:
                        writeLog('%s: no active player yet' % device.m_item['host'])
                else:
                    writeLog('%s seems to be offline' % host_name)
                    device.m_item.update({'symbol': get_media_symbol('offline'), 'label2': __LS__(30031)})

                wid = xbmcgui.ListItem(label=device.m_item['host'],
                                       label2=device.m_item['label2'], iconImage=device.m_item['thumb'])
                wid.setProperty('thumb', device.m_item['symbol'])
                if handle is not None: xbmcplugin.addDirectoryItem(handle=handle, url='', listitem=wid)

        if handle is not None:
            xbmcplugin.endOfDirectory(handle=handle, updateListing=True)
            xbmc.executebuiltin('Container.Refresh')
