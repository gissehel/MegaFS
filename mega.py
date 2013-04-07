#!/usr/bin/env python

from megaclient import MegaClient
import sys
import os
import json
import yaml
import pyaml
import getpass

# prepare for i18n
def _(value) :
    return value

def superable(cls) :
    '''Provide .__super in python 2.x classes without having to specify the current 
    class name each time super is used (DRY principle).'''
    name = cls.__name__
    super_name = '_%s__super' % (name,)
    setattr(cls,super_name,super(cls))
    return cls

class CLExitException(Exception) : pass

@superable
class CLRunnable(object) :
    """A class to handle command line parsing/executing"""
    def __init__(self) :
        self._args = None
        self._tool_name = None
        
    def status(self, message) :
        sys.stdout.write('%s\n' % (message,))

    def error(self, message) :
        sys.stderr.write(_("Error : %s\n") % (message,))


    def errorexit(self, message) :
        self.error(message)
        raise CLExitException()

    def help(self,args=[],kwargs={}) :
        tool_name = self._tool_name 
        if tool_name is None :
            tool_name = ''
        else :
            tool_name = tool_name + ' '

        print _("Usage: %sCOMMAND_NAME [OPTION] [VALUES]") % (tool_name,)
        if self._cl_params['doc'] is not None :
            print self._cl_params['doc']
        print ''
        if len(self._cl_params['commands'])>0 :
            print 'Commands:'
            names = sorted(set(self._cl_params['commands'][command_name]['name'] for command_name in self._cl_params['commands']))
            for name in names :
                command = self._cl_params['commands'][name]
                print '    %-20s %-40s' % (name, command['doc'] or '')
                if len(command['aliases'])>1 :
                    print '%s (%s)' % (' '*24,','.join(sorted(command['aliases'])))
            print ''
        if len(self._cl_params['params'])>0 :
            print 'General parameters:'
            names = sorted(set(self._cl_params['params'][param_name]['name'] for param_name in self._cl_params['params']))
            for name in names :
                param = self._cl_params['params'][name]
                print '    --%-18s %-40s' % (name, param['doc'] or '')
                if len(param['aliases'])>1 :
                    print '%s (%s)' % (' '*24,','.join(sorted(['-','--'][int(len(alias)>1)]+alias for alias in param['aliases'])))

            print ''

    def parse(self,args) :
        if len(args) == 0 :
            self.errorexit(_("Unexpected argument in parse method : first argument must be command line executable name"))
        self._tool_name = args[0]
        if self._tool_name in ('',None) :
            self._tool_name = None
        else :
            self._tool_name = os.path.basename(self._tool_name)

        if len(args) == 1 :
            self.help()
            self.errorexit(_("Need a command name"))
        else :
            command_name = args[1]
            needed_arguments = []
            if command_name in self._cl_params['commands'] :
                ordered_args = []
                dict_args = {}
                parameter_hooks = []
                command = self._cl_params['commands'][command_name]

                for arg in args[2:] :
                    if arg.startswith('--') :
                        if len(needed_arguments) > 0 :
                            (prev_arg_letter,prev_arg,prev_param) = needed_arguments[0]
                            self.errorexit(_("Switch [-%s] need parameter in [%s]") % (prev_arg_letter,prev_arg))
                        arg_parts = arg.split('=',1)
                        arg_name = arg_parts[0][2:]
                        if arg_name not in command['params'] :
                            if arg_name not in self._cl_params['params'] :
                                self.errorexit(_("Don't know [%s] in param [%s]" % (arg_name, arg)))
                            else :
                                param = self._cl_params['params'][arg_name]
                        else :
                            param = command['params'][arg_name]

                        dict_args[param['name']] = arg_parts[1] if len(arg_parts) > 1 else param['default']
                        if param['code'] is not None :
                            parameter_hooks.append((param['code'],param['name'],dict_args[param['name']]))

                    elif arg.startswith('-') and len(arg)>1 :
                        if len(needed_arguments) > 0 :
                            (prev_arg_letter,prev_arg,prev_param) = needed_arguments[0]
                            self.errorexit(_("Switch [-%s] need parameter in [%s]") % (prev_arg_letter,prev_arg))
                        for arg_letter in arg[1:] :
                            if arg_letter not in command['params'] :
                                if arg_letter not in self._cl_params['params'] :
                                    self.errorexit(_("Don't know [%s] in switch [%s]") % (arg_letter, arg))
                                else :
                                    param = self._cl_params['params'][arg_letter]
                            else :
                                param = command['params'][arg_letter]

                            if param['need_value'] :
                                needed_arguments.append((arg_letter,arg,param))
                            else :
                                dict_args[param['name']] = param['default']
                                if param['code'] is not None :
                                    parameter_hooks.append((param['code'],param['name'],dict_args[param['name']]))
                    else :
                        if len(needed_arguments) > 0 :
                            (prev_arg_letter,prev_arg,prev_param) = needed_arguments[0]
                            dict_args[prev_param['name']] = arg
                            if prev_param['code'] is not None :
                                parameter_hooks.append((prev_param['code'],prev_param['name'],dict_args[prev_param['name']]))

                            needed_arguments.pop(0)
                        else :
                            ordered_args.append(arg)
                if len(needed_arguments) > 0 :
                    (prev_arg_letter,prev_arg,prev_param) = needed_arguments[0]
                    self.errorexit(_("Switch [-%s] need parameter in [%s]") % (prev_arg_letter,prev_arg))
                for code, name, value in parameter_hooks :
                    code(self, args=ordered_args, kwargs=dict_args, name=name, value=value)
                command['code'](self,args=ordered_args,kwargs=dict_args)
            else :
                self.help()
                self.errorexit(_("No command named [%s]") % (command_name,))
            
    def run(self,args) :
        try :
            self.parse(args)
        except CLExitException :
            return False
        return True

@superable
class ConfigurableCLRunnable(CLRunnable) :
    """A subclass of CLRunnable that provide configuration file reading/writing"""
    def __init__(self, config_dirname, config_filename) :
        self.__super.__init__()
        self._configuration_dirname = os.path.expanduser(config_dirname)
        self._configuration_filename = os.path.join(self._configuration_dirname, config_filename)
        self.load_config()

    def export_config(self) :
        return {}

    def import_config(self,config) :
        pass

    def save_config(self) :
        if not(os.path.exists(self._configuration_dirname)) :
            os.makedirs(self._configuration_dirname,mode=0700);
        config = self.export_config()
        with open(self._configuration_filename,'wb') as handle :
            json.dump(config,handle,indent=2)

    def load_config(self) :
        if os.path.exists(self._configuration_filename) :
            with open(self._configuration_filename,'rb') as handle :
                config = json.load(handle)
            self.import_config(config)
    def run(self, args) :
        try :
            return self.__super.run(args)
        finally :
            self.save_config()

class CLRunner(object) :
    """A class that provide decorators to transform a class into a command line tool"""
    @staticmethod
    def _normalize_param(param,name=None) :
            if param is None :
                param = {}
            new_param = {}
            new_param['name'] = name
            new_param['need_value'] = param['need_value'] if ('need_value' in param) else False
            new_param['default'] = param['default'] if ('default' in param) else None
            new_param['aliases'] = [name] + (param['aliases'] if 'aliases' in param else [])
            new_param['doc'] = param['doc'] if ('doc' in param) else None
            new_param['code'] = param['code'] if ('code' in param) else None
            return new_param

    @staticmethod
    def _normalize_params(params) :
        new_params = {}
        for name in params :
            param = params[name]
            new_param = CLRunner._normalize_param(param,name)
            for alias in new_param['aliases'] :
                new_params[alias] = new_param
        return new_params

    @staticmethod
    def param(**kwargs) :
        def result(method) :
            param = CLRunner._normalize_param( kwargs, kwargs['name'] if 'name' in kwargs else method.func_name )
            if param['doc'] is None :
                param['doc'] = method.func_doc
            method._cl_param = param
            return method
        return result

    @staticmethod
    def command(name=None,params=None,aliases=None,doc=None) :
        def result(method) :
            command_name = method.func_name if name is None else name
            command_doc = method.func_doc if doc is None else doc
            method._cl_command = {
                'name' : command_name,
                'params' : CLRunner._normalize_params( {} if params is None else params ),
                'aliases' : [command_name] if aliases is None else [command_name] + aliases,
                'doc' : command_doc,
                }
            return method
        return result

    @staticmethod
    def runnable(name=None,params={},runnable=None,runnable_args=None,runnable_kwargs=None,doc=None) :
        if runnable is None :
            runnable = CLRunnable
        if runnable_args is None :
            runnable_args = []
        if runnable_kwargs is None :
            runnable_kwargs = {}
        def result(cls) :
            class command_line_runnable(cls, runnable) :
                def __init__(self, *args, **kwargs) :
                    cls.__init__(self, *args, **kwargs)
                    runnable.__init__(self,*runnable_args,**runnable_kwargs)
            runnable_name = cls.__name__ if name is None else name
            commands = {}
            global_params = CLRunner._normalize_params(params)

            for attrname in dir(command_line_runnable) :
                item = getattr(command_line_runnable,attrname)
                if hasattr(item,'_cl_command') :
                    command = {
                        'name' : item._cl_command['name'],
                        'params' : item._cl_command['params'],
                        'aliases' : item._cl_command['aliases'],
                        'doc' : item._cl_command['doc'] if item._cl_command['doc'] is not None else item.func_doc,
                        'code' : item,
                        }
                    delattr(item.im_func,'_cl_command')
                    for alias in command['aliases'] :
                        commands[alias] = command
                if hasattr(item,'_cl_param') :
                    param = item._cl_param
                    param['code'] = item
                    delattr(item.im_func,'_cl_param')
                    for alias in param['aliases'] :
                        global_params[alias] = param

            command_line_runnable.__name__ = cls.__name__

            command_line_runnable._cl_params = {
                'name' : runnable_name,
                'params' : global_params,
                'commands' : commands,
                'doc' :  cls.__doc__ if doc is None else doc,
                }
            # print yaml.dump(command_line_runnable._cl_params,default_flow_style=False)
            return command_line_runnable
        return result

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
        self.status('logged out')

    @CLRunner.command()
    def ls(self, args, kwargs) :
        """list files on mega"""
        #self.login([],{})
        client = self.get_client()
        files = client.getfiles()

        print pyaml.dump(files,sys.stdout)
        print len(files)

if __name__ == '__main__' :
    megaclparser = MegaCommandLineClient()
    if not(megaclparser.run( sys.argv )) :
        sys.exit(1)




