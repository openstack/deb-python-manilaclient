# Copyright 2014 Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import time

import six
from tempest_lib.cli import base
from tempest_lib.cli import output_parser
from tempest_lib.common.utils import data_utils
from tempest_lib import exceptions as tempest_lib_exc

from manilaclient.tests.functional import exceptions

SHARE_TYPE = 'share_type'


class ManilaCLIClient(base.CLIClient):

    def manila(self, action, flags='', params='', fail_ok=False,
               endpoint_type='publicURL', merge_stderr=False):
        """Executes manila command for the given action.

        :param action: the cli command to run using manila
        :type action: string
        :param flags: any optional cli flags to use
        :type flags: string
        :param params: any optional positional args to use
        :type params: string
        :param fail_ok: if True an exception is not raised when the
                        cli return code is non-zero
        :type fail_ok: boolean
        :param endpoint_type: the type of endpoint for the service
        :type endpoint_type: string
        :param merge_stderr: if True the stderr buffer is merged into stdout
        :type merge_stderr: boolean
        """
        flags += ' --endpoint-type %s' % endpoint_type
        return self.cmd_with_auth(
            'manila', action, flags, params, fail_ok, merge_stderr)

    def wait_for_resource_deletion(self, res_type, res_id, interval=3,
                                   timeout=180):
        """Resource deletion waiter.

        :param res_type: text -- type of resource. Supported only 'share_type'.
            Other types support is TODO.
        :param res_id: text -- ID of resource to use for deletion check
        :param interval: int -- interval between requests in seconds
        :param timeout: int -- total time in seconds to wait for deletion
        """
        # TODO(vponomaryov): add support for other resource types
        if res_type == SHARE_TYPE:
            func = self.is_share_type_deleted
        else:
            raise exceptions.InvalidResource(message=res_type)

        end_loop_time = time.time() + timeout
        deleted = func(res_id)

        while not (deleted or time.time() > end_loop_time):
            time.sleep(interval)
            deleted = func(res_id)

        if not deleted:
            raise exceptions.ResourceReleaseFailed(
                res_type=res_type, res_id=res_id)

    def create_share_type(self, name=None, driver_handles_share_servers=True,
                          is_public=True):
        """Creates share type.

        :param name: text -- name of share type to use, if not set then
            autogenerated will be used
        :param driver_handles_share_servers: bool/str -- boolean or its
            string alias. Default is True.
        :param is_public: bool/str -- boolean or its string alias. Default is
            True.
        """
        if name is None:
            name = data_utils.rand_name('manilaclient_functional_test')
        dhss = driver_handles_share_servers
        if not isinstance(dhss, six.string_types):
            dhss = six.text_type(dhss)
        if not isinstance(is_public, six.string_types):
            is_public = six.text_type(is_public)
        cmd = 'type-create %(name)s %(dhss)s --is-public %(is_public)s' % {
            'name': name, 'dhss': dhss, 'is_public': is_public}
        share_type_raw = self.manila(cmd)

        # NOTE(vponomaryov): share type creation response is "list"-like with
        # only one element:
        # [{
        #   'ID': '%id%',
        #   'Name': '%name%',
        #   'Visibility': 'public',
        #   'is_default': '-',
        #   'required_extra_specs': 'driver_handles_share_servers : False',
        # }]
        share_type = output_parser.listing(share_type_raw)[0]
        return share_type

    def delete_share_type(self, share_type):
        """Deletes share type by its Name or ID."""
        try:
            return self.manila('type-delete %s' % share_type)
        except tempest_lib_exc.CommandFailed as e:
            not_found_msg = 'No sharetype with a name or ID'
            if not_found_msg in e.stderr:
                # Assuming it was deleted in tests
                raise tempest_lib_exc.NotFound()
            raise

    def list_share_types(self, list_all=True):
        """List share types.

        :param list_all: bool -- whether to list all share types or only public
        """
        cmd = 'type-list'
        if list_all:
            cmd += ' --all'
        share_types_raw = self.manila(cmd)
        share_types = output_parser.listing(share_types_raw)
        return share_types

    def is_share_type_deleted(self, share_type):
        """Says whether share type is deleted or not.

        :param share_type: text -- Name or ID of share type
        """
        # NOTE(vponomaryov): we use 'list' operation because there is no
        # 'get/show' operation for share-types available for CLI
        share_types = self.list_share_types(list_all=True)
        for list_element in share_types:
            if share_type in (list_element['ID'], list_element['Name']):
                return False
        return True

    def wait_for_share_type_deletion(self, share_type):
        """Wait for share type deletion by its Name or ID.

        :param share_type: text -- Name or ID of share type
        """
        self.wait_for_resource_deletion(
            SHARE_TYPE, res_id=share_type, interval=2, timeout=6)

    def get_project_id(self, name_or_id):
        project_id = self.openstack(
            'project show -f value -c id %s' % name_or_id)
        return project_id.strip()

    def add_share_type_access(self, share_type_name_or_id, project_id):
        data = dict(st=share_type_name_or_id, project=project_id)
        self.manila('type-access-add %(st)s %(project)s' % data)

    def remove_share_type_access(self, share_type_name_or_id, project_id):
        data = dict(st=share_type_name_or_id, project=project_id)
        self.manila('type-access-remove %(st)s %(project)s' % data)

    def list_share_type_access(self, share_type_id):
        projects_raw = self.manila('type-access-list %s' % share_type_id)
        projects = output_parser.listing(projects_raw)
        project_ids = [pr['Project_ID'] for pr in projects]
        return project_ids
