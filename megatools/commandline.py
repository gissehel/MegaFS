#!/usr/bin/env python

from megaclient import MegaClient
import sys
import os
import time
import json
import yaml
import pyaml
import shutil
import getpass
import posixpath

from supertools import superable
from cltools import _
from cltools import ConfigurableCLRunnable
from cltools import CLRunner

@CLRunner.runnable(
    runnable=ConfigurableCLRunnable,
    runnable_kwargs={
        'config_dirname' : '~/.megaclient',
        'config_filename' : 'config',
        },
    )
@superable
class MegaCommandLineClient(object) :
    """A command line tool for mega.co.nz"""
    def __init__(self) :
        self._sid = ''
        self._master_key = None
        self._email = None
        self._client = None
        self._seqno = None

        self._root = None

    def export_config(self) :
        if self._client is not None :
            self._seqno = self._client.seqno
        return {
            'sid' : self._sid,
            'master_key' : self._master_key,
            'email' : self._email,
            'seqno' : self._seqno,
            }

    def import_config(self,config) :
        self._sid = config.get('sid','')
        self._email = config.get('email',None)
        self._master_key = config.get('master_key',None)
        self._seqno = config.get('seqno',None)

    def get_client(self) :
        if (self._client is None) and (self._sid != '') :
            self._client = MegaClient(self._email,None)
            self._client.sid = self._sid
            self._client.master_key = self._master_key
            self._client.seqno = self._seqno
        return self._client

    @CLRunner.param(aliases=['d'])
    def debug(self, **kwargs) :
        '''Provide some debug informations'''
        self.help()
        print yaml.dump(self._cl_params,default_flow_style=False)

    @CLRunner.param(name='help',aliases=['h'])
    def help_command(self,name,value,**kwargs) :
        '''Get help on specific command'''
        print "!!%r=%r" % (name,value)

    @CLRunner.command()
    def help(self, args=[], kwargs={}) :
        """give help"""
        self.__super.help()

    @CLRunner.command(params={
        'email':{
            'need_value' : True,
            'aliases' : ['e'],
            },
        })
    def login(self,args,kwargs) :
        """login to mega"""
        if 'email' in kwargs :
            self._email = kwargs['email']
            self.save_config()
        elif len(args) > 0 :
            self._email = args[0]
            self.save_config()
        if self._email is None :
            self.errorexit(_('need email to login'))
        sys.stdout.write('Login : [%s]\n' % (self._email,))
        password = getpass.getpass()
        if len(password) == 0 :
            self.errorexit(_('need a password to login'))
            
        self._client = MegaClient(self._email,password)
        try :
            self._client.login()
        except Exception :
            self.errorexit(_('login failled'))
        self._sid = self._client.sid
        self._master_key = self._client.master_key
        self.save_config()

        self.status('login success')

    @CLRunner.command()
    def logout(self,args,kwargs) :
        """logout from mega"""
        if self._sid != '' or self._master_key != '' :
            self._master_key = ''
            self._sid = ''
            self._seqno = None
            self.save_config()
            self._root = None
            self.del_stream('root')
        self.status('logged out')

    def get_root(self) :
        if self._root is not None :
            return self._root
        client = self.get_client()
        files = client.getfiles()
        root = {}
        root['files'] = files
        root['tree'] = {}
        root['path'] = {}
        treeitems = {}
        for handle in files :
            file = files[handle]
            if handle not in treeitems :
                treeitems[handle] = {}
                treeitems[handle]['h'] = handle
            treeitem = treeitems[handle]
            if 'p' in file and file['p'] in files :
                phandle = file['p']
                if phandle not in treeitems :
                    treeitems[phandle] = {}
                    treeitems[phandle]['h'] = phandle
                ptreeitem = treeitems[phandle]
                if 'children' not in ptreeitem :
                    ptreeitem['children'] = {}
                ptreeitem['children'][handle] = treeitem
            else :
                root['tree'][handle] = treeitem
        def updatepath(dictchildren, parentpath, level) :
            for treeitem in dictchildren.values() :
                node = files[treeitem['h']]
                if not(node['a']) :
                    node['a'] = { 'n' : '?(%s)' % (node['h'],) }
                node['a']['path'] = posixpath.join(parentpath,node['a']['n'])
                node['a']['level'] = level
                root['path'][ node['a']['path'] ] = node['h']
                if 'children' in treeitem :
                    updatepath(treeitem['children'],node['a']['path'],level+1)
        updatepath(root['tree'],'/',0)
        self.save_stream('root',root)
        self._root = root
        return self._root

    @CLRunner.command(params={
        'filter' : {
            'need_value' : True,
            'aliases' : ['f'],
            },
        })
    def find(self, args, kwargs) :
        """list files on mega"""
        root = self.get_root()
        for path in sorted(root['path']) :
            node = root['files'][root['path'][path]]
            if ('filter' not in kwargs) or (kwargs['filter'].lower() in node['a']['path'].lower()) :
                self.status("%s '%s'" % (node['h'],node['a']['path']))

    @CLRunner.command(params={
        'filter' : {
            'need_value' : True,
            'aliases' : ['f'],
            },
        })
    def show(self, args, kwargs) :
        """list files on mega"""
        root = self.get_root()
        for path in sorted(root['path']) :
            node = root['files'][root['path'][path]]
            if ('filter' not in kwargs) or (kwargs['filter'].lower() in node['a']['n'].lower()) :
                self.status("%s %s'%s'" % (node['h'],'  '*node['a']['level'], node['a']['n']))

    @CLRunner.command()
    def get(self, args, kwargs) :
        """get a file"""
        root = self.get_root()
        if len(args) == 0 :
            self.errorexit(_('Need a file handle to download'))
        handle = args[0]
        if handle not in root['files'] :
            self.errorexit(_('No file with handle [%s]')%(handle,))
        node = root['files'][handle]
        filename = node['a']['n']
        tmp_filename = '.mega-%s-%s' % (int(time.time()*1000),filename)
        self.status(_('Getting [%s]')%(filename,))

        client = self.get_client()
        client.downloadfile(node,tmp_filename)

        shutil.move(tmp_filename, filename)


    @CLRunner.command()
    def put(self, args, kwargs) :
        """put a file"""
        root = self.get_root()
        if len(args) < 2 :
            self.errorexit(_('Need a file to upload and a directory handle where to upload'))
        filename = args[0]
        dhandle = args[1]
        if not(os.path.exists(filename)) :
            self.errorexit(_("File [%s] doesn't exist")%(filename,))
        if dhandle not in root['files'] :
            self.errorexit(_("No directory handle named [%s]")%(dhandle,))
        node = root['files'][dhandle]
        if node['t'] != 1 :
            self.errorexit(_("The handle [%s] must be a directory handle. [%s] is not a directory")%(dhandle, node['a']['n'],))
        
        client = self.get_client()
        dirname, basename = os.path.split(filename)
        client.uploadfile(filename, node['h'], basename)


    @CLRunner.command()
    def reload(self, args, kwargs) :
        """reload the filesystem"""
        self._root = None
        self.del_stream('root')
        self.get_root()





