from __future__ import unicode_literals

import StringIO
import os
import tempfile
import zipfile

from datetime import datetime

import requests

from django.db import models
from mrbelvedereci.cumulusci.config import MrbelvedereGlobalConfig
from mrbelvedereci.cumulusci.config import MrbelvedereProjectConfig
from mrbelvedereci.cumulusci.keychain import MrbelvedereProjectKeychain

from cumulusci.core.config import FlowConfig
from cumulusci.core.exceptions import FlowNotFoundError
from cumulusci.core.utils import import_class

BUILD_STATUSES = (
    ('queued', 'Queued'),
    ('running', 'Running'),
    ('success', 'Success'),
    ('error', 'Error'),
    ('fail', 'Failed'),
)
BUILD_FLOW_STATUSES = (
    ('queued', 'Queued'),
    ('running', 'Running'),
    ('success', 'Success'),
    ('error', 'Error'),
    ('fail', 'Failed'),
)

class Build(models.Model):
    repo = models.ForeignKey('github.Repository', related_name='builds')
    branch = models.ForeignKey('github.Branch', related_name='builds', null=True, blank=True)
    commit = models.CharField(max_length=64)
    tag = models.CharField(max_length=255, null=True, blank=True)
    pr = models.IntegerField(null=True, blank=True)
    trigger = models.ForeignKey('trigger.Trigger', related_name='builds')
    log = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=BUILD_STATUSES, default='queued')
    current_flow_index = models.IntegerField(default=0)
    time_queue = models.DateTimeField(auto_now_add=True)
    time_start = models.DateTimeField(null=True, blank=True)
    time_end = models.DateTimeField(null=True, blank=True) 

    def __unicode__(self):
        return '{}: {} - {}'.format(self.id, self.repo, self.commit)

    def run(self):
        self.set_running_status()

        flows = [flow.strip() for flow in self.trigger.flows.split(',')]
        for flow in flows:
            build_flow = BuildFlow(
                build = self,
                flow = flow,
            )
            build_flow.save()
            build_flow.run()
        self.status = 'success'
        self.save()

    def set_running_status(self): 
        self.status = 'running'
        self.time_start = datetime.now()
        if self.log is None:
            self.log = ''
        self.log += '-- Building commit {}\n'.format(self.commit)
        self.save()

class BuildFlow(models.Model):
    build = models.ForeignKey('build.Build', related_name='steps')
    status = models.CharField(max_length=16, choices=BUILD_FLOW_STATUSES, default='queued')
    flow = models.CharField(max_length=255, null=True, blank=True)
    log = models.TextField(null=True, blank=True)
    time_queue = models.DateTimeField(auto_now_add=True)
    time_start = models.DateTimeField(null=True, blank=True)
    time_end = models.DateTimeField(null=True, blank=True) 

    def run(self):
        # Record the start
        self.set_running_status()

        # Extract the repo to a temp build dir
        self.build_dir = self.checkout()

        # Change directory to the build_dir
        os.chdir(self.build_dir)

        # Initialize the project config
        project_config = self.get_project_config()

        # Look up the org
        org_config = self.get_org(project_config)

        # Run the flow
        result = self.run_flow(project_config, org_config)

        # Record result
        self.record_result(result)
        
       
    def set_running_status(self): 
        self.status = 'running'
        self.time_start = datetime.now()
        if self.log is None:
            self.log = ''
        self.log += '-- Running flow: {}\n'.format(self.flow)
        self.save()

    def checkout(self):
        zip_url = '{}/archive/{}.zip'.format(
            self.build.repo.url,
            self.build.commit,
        )
        self.log += '-- Download commit from Github URL:\n     {}\n'.format(zip_url)
        self.save()
        resp = requests.get(zip_url)
        build_dir = tempfile.mkdtemp()
        self.log += '-- Extracting zip to temp dir:\n     {}\n'.format(build_dir)
        self.save()
        zip_content = StringIO.StringIO(resp.content)
        zip_file = zipfile.ZipFile(zip_content)
        zip_file.extractall(build_dir)
        build_dir += '/{}-{}'.format(self.build.repo.name, self.build.commit)
        self.log += '-- Commit extracted to build dir:\n     {}\n'.format(build_dir)
        self.save()
        return build_dir

    def get_project_config(self):
        global_config = MrbelvedereGlobalConfig()
        project_config = global_config.get_project_config(self)
        keychain = MrbelvedereProjectKeychain(project_config, None, self)
        project_config.set_keychain(keychain)
        return project_config

    def get_org(self, project_config):
        org = project_config.keychain.get_org(self.build.trigger.org)
        return org

    def run_flow(self, project_config, org_config):
        flow = getattr(project_config, 'flows__{}'.format(self.flow))
        if not flow:
            raise FlowNotFoundError('Flow not found: {}'.format(flow_name))
        flow_config = FlowConfig(flow)
    
        # Get the class to look up options
        class_path = flow_config.config.get('class_path', 'cumulusci.core.flows.BaseFlow')
        flow_class = import_class(class_path)
    
        exception = None
    
        # Create the flow and handle initialization exceptions
        flow = flow_class(project_config, flow_config, org_config)
        return flow()
    
    def record_result(self, result):
        pass
