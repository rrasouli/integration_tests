# -*- coding: utf-8 -*-
import pytest
import requests

import cfme.fixtures.pytest_selenium as sel
from cfme.utils.appliance.implementations.ui import navigate_to


@pytest.mark.tier(3)
def test_verify_rss_links(appliance):
    view = navigate_to(appliance.server, 'RSS')
    for row in view.table.rows():
        url = row[3].text
        req = requests.get(url, verify=False)
        assert 200 <= req.status_code < 400, "The url {} seems malformed".format(repr(url))
