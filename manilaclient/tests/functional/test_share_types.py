# Copyright 2015 Mirantis Inc.
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

import ddt
from tempest_lib.common.utils import data_utils

from manilaclient.tests.functional import base


@ddt.ddt
class ShareTypesReadOnlyTest(base.BaseTestCase):

    @ddt.data('admin', 'user')
    def test_share_type_list(self, role):
        self.clients[role].manila('type-list')

    def test_extra_specs_list(self):
        self.admin_client.manila('extra-specs-list')


@ddt.ddt
class ShareTypesReadWriteTest(base.BaseTestCase):

    create_keys = (
        'ID', 'Name', 'Visibility', 'is_default', 'required_extra_specs')

    def _share_type_listed_by(self, share_type_id, by_admin=False,
                              list_all=False):
        if by_admin:
            client = self.admin_client
        else:
            client = self.user_client
        share_types = client.list_share_types(list_all=list_all)
        return any(share_type_id == st['ID'] for st in share_types)

    def _verify_access(self, share_type_id, is_public):
        if is_public:
            # Verify that it is listed with common 'type-list' operation.
            share_types = self.admin_client.list_share_types(list_all=False)
            self.assertTrue(
                any(share_type_id == st['ID'] for st in share_types))
        else:
            # Verify that it is not listed for user
            self.assertFalse(self._share_type_listed_by(
                share_type_id=share_type_id, by_admin=False, list_all=True))

            # Verify it is listed for admin
            self.assertTrue(self._share_type_listed_by(
                share_type_id=share_type_id, by_admin=True, list_all=True))

            # Verify it is not listed by default
            self.assertFalse(self._share_type_listed_by(
                share_type_id=share_type_id, by_admin=True, list_all=False))

    @ddt.data(
        {'is_public': True, 'dhss': False},
        {'is_public': True, 'dhss': True},
        {'is_public': False, 'dhss': True},
        {'is_public': False, 'dhss': False},
    )
    @ddt.unpack
    def test_create_delete_share_type(self, is_public, dhss):
        share_type_name = data_utils.rand_name('manilaclient_functional_test')
        dhss_expected = 'driver_handles_share_servers : %s' % dhss

        # Create share type
        share_type = self.create_share_type(
            name=share_type_name,
            driver_handles_share_servers=dhss,
            is_public=is_public)

        st_id = share_type['ID']

        # Verify response body
        for key in self.create_keys:
            self.assertIn(key, share_type)
        self.assertEqual(share_type_name, share_type['Name'])
        self.assertEqual(dhss_expected, share_type['required_extra_specs'])
        self.assertEqual('public' if is_public else 'private',
                         share_type['Visibility'].lower())
        self.assertEqual('-', share_type['is_default'])

        # Verify its access
        self._verify_access(share_type_id=st_id, is_public=is_public)

        # Delete share type
        self.admin_client.delete_share_type(st_id)

        # Wait for share type deletion
        self.admin_client.wait_for_share_type_deletion(st_id)

        # Verify that it is not listed with common 'type-list' operation.
        share_types = self.admin_client.list_share_types(list_all=False)
        self.assertFalse(
            any(st_id == st['ID'] for st in share_types))

    def test_add_remove_access_to_private_share_type(self):
        share_type_name = data_utils.rand_name('manilaclient_functional_test')
        is_public = False

        # Create share type
        share_type = self.create_share_type(
            name=share_type_name,
            driver_handles_share_servers='False',
            is_public=is_public)

        st_id = share_type['ID']
        user_project_id = self.admin_client.get_project_id(
            self.user_client.tenant_name)

        self._verify_access(share_type_id=st_id, is_public=is_public)

        # Project ID is in access list - false
        st_access_list = self.admin_client.list_share_type_access(st_id)
        self.assertNotIn(user_project_id, st_access_list)

        # Add access for project of user
        self.admin_client.add_share_type_access(st_id, user_project_id)

        # Verify it is listed for user as well as for admin
        self.assertTrue(self._share_type_listed_by(
            share_type_id=st_id, by_admin=False, list_all=True))
        self.assertTrue(self._share_type_listed_by(
            share_type_id=st_id, by_admin=True, list_all=True))

        # Project ID is in access list - true
        st_access_list = self.admin_client.list_share_type_access(st_id)
        self.assertIn(user_project_id, st_access_list)

        # Remove access
        self.admin_client.remove_share_type_access(st_id, user_project_id)

        self._verify_access(share_type_id=st_id, is_public=is_public)

        # Project ID is in access list - false
        st_access_list = self.admin_client.list_share_type_access(st_id)
        self.assertNotIn(user_project_id, st_access_list)
