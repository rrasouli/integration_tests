# -*- coding: utf-8 -*-
import pytest

import fauxfactory

from cfme import test_requirements
from cfme.cloud.provider import CloudProvider
from cfme.common.vm import VM
from cfme.infrastructure.provider import CloudInfraProvider, InfraProvider
from cfme.utils import error
from cfme.utils.blockers import BZ
from cfme.utils.generators import random_vm_name
from cfme.utils.log import logger
from cfme.utils.rest import assert_response, delete_resources_from_collection
from cfme.utils.version import current_version


pytestmark = [
    pytest.mark.long_running,
    pytest.mark.tier(2),
    pytest.mark.provider([CloudInfraProvider], scope='module'),
    test_requirements.rest
]

COLLECTIONS = ['providers', 'instances', 'vms']
COLLECTIONS_ADDED_IN_59 = ['instances', 'vms']


@pytest.yield_fixture(scope='module')
def vm_obj(provider, setup_provider_modscope, small_template_modscope):
    """Creates new VM or instance"""
    vm_name = random_vm_name('attrs')
    new_vm = VM.factory(vm_name, provider, template_name=small_template_modscope.name)

    if not provider.mgmt.does_vm_exist(vm_name):
        new_vm.create_on_provider(find_in_cfme=True, allow_skip='default')

    yield new_vm

    try:
        provider.mgmt.delete_vm(new_vm.name)
    except Exception:
        logger.warning('Failed to delete vm `{}`.'.format(new_vm.name))


@pytest.fixture(scope='module')
def providers(appliance, provider, setup_provider_modscope):
    resource = appliance.rest_api.collections.providers.get(name=provider.name)
    return resource


@pytest.fixture(scope='module')
def instances(appliance, provider, vm_obj):
    if provider.one_of(InfraProvider):
        return
    resource = appliance.rest_api.collections.instances.get(name=vm_obj.name)
    return resource


@pytest.fixture(scope='module')
def vms(appliance, provider, vm_obj):
    if not provider.one_of(InfraProvider):
        return
    resource = appliance.rest_api.collections.vms.get(name=vm_obj.name)
    return resource


@pytest.fixture(scope='module')
def fixtures_db(providers, instances, vms):
    db = {
        'providers': providers,
        'instances': instances,
        'vms': vms
    }
    return db


def add_custom_attributes(request, resource):
    body = []
    attrs_num = 2
    for __ in range(attrs_num):
        uid = fauxfactory.gen_alphanumeric(5)
        body.append({
            'name': 'ca_name_{}'.format(uid),
            'value': 'ca_value_{}'.format(uid)
        })
    attrs = resource.custom_attributes.action.add(*body)

    @request.addfinalizer
    def _delete():
        resource.custom_attributes.reload()
        ids = [attr.id for attr in attrs]
        delete_attrs = [attr for attr in resource.custom_attributes if attr.id in ids]
        if delete_attrs:
            resource.custom_attributes.action.delete(*delete_attrs)

    assert_response(resource.collection._api)
    assert len(attrs) == attrs_num
    return attrs, resource


def _uncollectif(provider, collection_name):
    return (
        current_version() < '5.8' or
        (current_version() < '5.9' and collection_name in COLLECTIONS_ADDED_IN_59) or
        (provider.one_of(InfraProvider) and collection_name == 'instances') or
        (provider.one_of(CloudProvider) and collection_name == 'vms')
    )


class TestCustomAttributesRESTAPI(object):
    @pytest.mark.uncollectif(lambda provider, collection_name:
        _uncollectif(provider, collection_name)
    )
    @pytest.mark.parametrize("collection_name", COLLECTIONS)
    def test_add(self, request, collection_name, appliance, fixtures_db):
        """Test adding custom attributes to resource using REST API.

        Metadata:
            test_flag: rest
        """
        attributes, resource = add_custom_attributes(request, fixtures_db[collection_name])
        for attr in attributes:
            record = resource.custom_attributes.get(id=attr.id)
            assert record.name == attr.name
            assert record.value == attr.value

    @pytest.mark.uncollectif(lambda provider, collection_name:
        _uncollectif(provider, collection_name)
    )
    @pytest.mark.parametrize("collection_name", COLLECTIONS)
    def test_delete_from_detail_post(self, request, collection_name, appliance, fixtures_db):
        """Test deleting custom attributes from detail using POST method.

        Metadata:
            test_flag: rest
        """
        attributes, __ = add_custom_attributes(request, fixtures_db[collection_name])
        for entity in attributes:
            entity.action.delete.POST()
            assert_response(appliance)
            with error.expected('ActiveRecord::RecordNotFound'):
                entity.action.delete.POST()
            assert_response(appliance, http_status=404)

    @pytest.mark.uncollectif(lambda provider, collection_name:
        current_version() < '5.9' or  # BZ 1422596 was not fixed for versions < 5.9
        _uncollectif(provider, collection_name)
    )
    @pytest.mark.parametrize("collection_name", COLLECTIONS)
    def test_delete_from_detail_delete(self, request, collection_name, appliance, fixtures_db):
        """Test deleting custom attributes from detail using DELETE method.

        Metadata:
            test_flag: rest
        """
        attributes, __ = add_custom_attributes(request, fixtures_db[collection_name])
        for entity in attributes:
            entity.action.delete.DELETE()
            assert_response(appliance)
            with error.expected('ActiveRecord::RecordNotFound'):
                entity.action.delete.DELETE()
            assert_response(appliance, http_status=404)

    @pytest.mark.uncollectif(lambda provider, collection_name:
        _uncollectif(provider, collection_name)
    )
    @pytest.mark.parametrize("collection_name", COLLECTIONS)
    def test_delete_from_collection(self, request, collection_name, fixtures_db):
        """Test deleting custom attributes from collection using REST API.

        Metadata:
            test_flag: rest
        """
        attributes, resource = add_custom_attributes(request, fixtures_db[collection_name])
        collection = resource.custom_attributes
        delete_resources_from_collection(collection, attributes, not_found=True)

    @pytest.mark.uncollectif(lambda provider, collection_name:
        _uncollectif(provider, collection_name)
    )
    @pytest.mark.parametrize("collection_name", COLLECTIONS)
    def test_delete_single_from_collection(self, request, collection_name, fixtures_db):
        """Test deleting single custom attribute from collection using REST API.

        Metadata:
            test_flag: rest
        """
        attributes, resource = add_custom_attributes(request, fixtures_db[collection_name])
        attribute = attributes[0]
        collection = resource.custom_attributes
        delete_resources_from_collection(collection, [attribute], not_found=True)

    @pytest.mark.uncollectif(lambda provider, collection_name:
        _uncollectif(provider, collection_name)
    )
    @pytest.mark.parametrize("collection_name", COLLECTIONS)
    @pytest.mark.parametrize('from_detail', [True, False], ids=['from_detail', 'from_collection'])
    def test_edit(self, request, from_detail, collection_name, appliance, fixtures_db):
        """Test editing custom attributes using REST API.

        Metadata:
            test_flag: rest
        """
        attributes, resource = add_custom_attributes(request, fixtures_db[collection_name])
        response_len = len(attributes)
        body = []
        for __ in range(response_len):
            uid = fauxfactory.gen_alphanumeric(5)
            body.append({
                'name': 'ca_name_{}'.format(uid),
                'value': 'ca_value_{}'.format(uid),
                'section': 'metadata'
            })
        if from_detail:
            edited = []
            for i in range(response_len):
                edited.append(attributes[i].action.edit(**body[i]))
                assert_response(appliance)
        else:
            for i in range(response_len):
                body[i].update(attributes[i]._ref_repr())
            edited = resource.custom_attributes.action.edit(*body)
            assert_response(appliance)
        assert len(edited) == response_len
        for i in range(response_len):
            attributes[i].reload()
            assert edited[i].name == body[i]['name'] == attributes[i].name
            assert edited[i].value == body[i]['value'] == attributes[i].value
            assert edited[i].section == body[i]['section'] == attributes[i].section

    @pytest.mark.uncollectif(lambda provider, collection_name:
        _uncollectif(provider, collection_name)
    )
    @pytest.mark.parametrize("collection_name", COLLECTIONS)
    @pytest.mark.meta(blockers=[
        BZ(
            1516762,
            forced_streams=['5.9', 'upstream'],
            unblock=lambda collection_name: collection_name not in ('vms', 'instances')
        )])
    @pytest.mark.parametrize('from_detail', [True, False], ids=['from_detail', 'from_collection'])
    def test_bad_section_edit(self, request, from_detail, collection_name, appliance, fixtures_db):
        """Test that editing custom attributes using REST API and adding invalid section fails.

        Metadata:
            test_flag: rest
        """
        attributes, resource = add_custom_attributes(request, fixtures_db[collection_name])
        response_len = len(attributes)
        body = []
        for __ in range(response_len):
            body.append({'section': 'bad_section'})
        if from_detail:
            for i in range(response_len):
                with error.expected('Api::BadRequestError'):
                    attributes[i].action.edit(**body[i])
                assert_response(appliance, http_status=400)
        else:
            for i in range(response_len):
                body[i].update(attributes[i]._ref_repr())
            with error.expected('Api::BadRequestError'):
                resource.custom_attributes.action.edit(*body)
            assert_response(appliance, http_status=400)

    @pytest.mark.uncollectif(lambda provider, collection_name:
        _uncollectif(provider, collection_name)
    )
    @pytest.mark.parametrize("collection_name", COLLECTIONS)
    @pytest.mark.meta(blockers=[
        BZ(
            1516762,
            forced_streams=['5.9', 'upstream'],
            unblock=lambda collection_name: collection_name not in ('vms', 'instances')
        )])
    def test_bad_section_add(self, request, collection_name, appliance, fixtures_db):
        """Test adding custom attributes with invalid section to resource using REST API.

        Metadata:
            test_flag: rest
        """
        __, resource = add_custom_attributes(request, fixtures_db[collection_name])
        uid = fauxfactory.gen_alphanumeric(5)
        body = {
            'name': 'ca_name_{}'.format(uid),
            'value': 'ca_value_{}'.format(uid),
            'section': 'bad_section'
        }
        with error.expected('Api::BadRequestError'):
            resource.custom_attributes.action.add(body)
        assert_response(appliance, http_status=400)
