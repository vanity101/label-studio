"""DCP-50: real-size multipart import must not 500 on RawPostDataException."""

import json

import pytest
from data_import.uploader import load_tasks, uploaded_files
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http.request import RawPostDataException
from django.test import RequestFactory, override_settings
from organizations.models import Organization
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from tests.utils import make_project

pytestmark = pytest.mark.django_db


def _multipart_django_request(payload: bytes, name: str = 'tasks.json'):
    upload = SimpleUploadedFile(name, payload, content_type='application/json')
    return RequestFactory().post('/api/projects/1/import', {'file': upload})


def _drf_request(django_request):
    return Request(django_request, parsers=[MultiPartParser(), FormParser()])


def test_drf_files_raises_when_stream_started_without_body():
    django_request = _multipart_django_request(b'[{"data":{"text":"ok"}}]')
    django_request.read(1)
    assert django_request._read_started
    assert not hasattr(django_request, '_body')

    with pytest.raises(RawPostDataException):
        _ = _drf_request(django_request).FILES


def test_uploaded_files_does_not_reread_body_after_stream_started():
    django_request = _multipart_django_request(b'[{"data":{"text":"ok"}}]')
    django_request.read(1)
    files = uploaded_files(_drf_request(django_request))
    assert files is not None
    assert len(files) == 0


def test_uploaded_files_returns_django_files_after_post_parse():
    django_request = _multipart_django_request(b'[{"data":{"text":"ok"}}]')
    _ = django_request.POST
    assert 'file' in django_request.FILES
    files = uploaded_files(_drf_request(django_request))
    assert 'file' in files
    assert files['file'].name == 'tasks.json'


def test_load_tasks_uses_django_files_after_csrf_style_post_parse():
    user = get_user_model().objects.create(email='dcp50-import@localhost')
    org = Organization.create_organization(created_by=user, title='dcp50')
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    project = make_project({}, user, use_ml_backend=False, org=org)

    payload = json.dumps([{'data': {'text': 'hello'}}]).encode()
    django_request = _multipart_django_request(payload)
    _ = django_request.POST
    drf_request = _drf_request(django_request)
    drf_request.user = user

    tasks, file_upload_ids, *_ = load_tasks(drf_request, project)

    assert len(tasks) == 1
    assert tasks[0]['data']['text'] == 'hello'
    assert file_upload_ids


@override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=64)
def test_import_api_oversized_multipart_does_not_500_body_stream(setup_project_dialog):
    """Full middleware + ImportAPI path: payload bigger than the in-memory body cache.

    940MB episode hdf5 hits the same class of failure on 7f7be424: ContextLog
    membership/`request.body` starts the stream, then DRF re-reads body.
    """
    payload = json.dumps([{'data': {'text': 'hello from dcp-50 ' + ('x' * 80)}}]).encode()
    assert len(payload) > 64
    endpoint = f'/api/projects/{setup_project_dialog.project.id}/import?commit_to_project=false'
    response = setup_project_dialog.post(
        endpoint,
        {'tasks.json': SimpleUploadedFile('tasks.json', payload, content_type='application/json')},
    )
    assert response.status_code == 201, response.content
    detail = str(getattr(response, 'data', response.content))
    assert 'data stream' not in detail
    assert response.data.get('file_upload_ids')
