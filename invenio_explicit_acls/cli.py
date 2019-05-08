#
# Copyright (c) 2019 UCT Prague.
# 
# cli.py is part of Invenio Explicit ACLs 
# (see https://github.com/oarepo/invenio-explicit-acls).
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
"""Command-line client extension."""

import json
import sys

import click
from flask import cli
from invenio_db import db
from invenio_indexer.api import RecordIndexer
from invenio_jsonschemas import current_jsonschemas
from invenio_records import Record
from invenio_records.models import RecordMetadata
from sqlalchemy import cast

from invenio_explicit_acls.models import ACL
from invenio_explicit_acls.proxies import current_explicit_acls


@click.group(name='explicit-acls')
def explicit_acls():
    """Invenio ACLs commands."""


@explicit_acls.command()
@click.argument('schema')
@cli.with_appcontext
def prepare(schema):
    """
        Setup schema to be used with invenio explicit acls.

    :param schema:       the name of the schema that should be prepared for explicit ACLs
    """
    current_explicit_acls.prepare(schema)


@explicit_acls.command()
@cli.with_appcontext
def list_schemas():
    """List all schemas registered in invenio."""
    for schema in current_jsonschemas.list_schemas():
        print("   ", schema)


@explicit_acls.command(name='full-reindex')
@click.option('--verbose/--no-verbose', default=False)
@click.option('--records/--no-records', default=True)
@cli.with_appcontext
def full_reindex(verbose, records):
    """Updates index of all ACLs and optionally reindexes all documents"""
    # 1. for each ACL update the ACL's index etc
    if verbose:
        print('Reindexing ACLs')
    for acl in ACL.query.all():
        if verbose:
            print('Updating ACL representation for', acl)
        acl.update()
    if not records:
        return
    # 2. for each of ACL enabled indices reindex all documents
    uuids = set()
    import sqlalchemy.dialects.postgresql
    for schema in current_explicit_acls.enabled_schemas:
        if verbose:
            print('Getting records for schema', schema)
        full_schema = current_jsonschemas.path_to_url(schema)
        # filter all records with the given schema
        recs = set()
        recs.update(str(x[0]) for x in db.session.query(RecordMetadata.id).filter(
            RecordMetadata.json['$schema'] == cast(schema, sqlalchemy.dialects.postgresql.JSONB)
        ))
        recs.update(str(x[0]) for x in db.session.query(RecordMetadata.id).filter(
            RecordMetadata.json['$schema'] == cast(full_schema, sqlalchemy.dialects.postgresql.JSONB)
        ))
        if verbose:
            print('   ... collected %s records' % len(recs))
        uuids.update(recs)

    if verbose:
        print('Adding %s records to indexing queue' % len(uuids))
    RecordIndexer().bulk_index(uuids)

    if verbose:
        print('Running bulk indexer on %s records' % len(uuids))
    RecordIndexer(version_type=None).process_bulk_queue(
        es_bulk_kwargs={'raise_on_error': False})


@explicit_acls.command()
@click.argument('record')
@cli.with_appcontext
def explain(record):
    """
    Explains which ACLs will be applied to a record and what the added ACL property will look like.

    :param record a path to a file containing record metadata or '-' to read the metadata from stdin.
    """
    class Model:
        def __init__(self):
            self.id = 'record-id'

    with open(record, 'r') if record is not "-" else sys.stdin as f:
        record_metadata = json.load(f)
        if '$schema' not in record_metadata:
            print('Please add $schema to record metadata')
            return
        invenio_record = Record(record_metadata)
        invenio_record.model = Model()

        applicable_acls = []
        for acl in current_explicit_acls.acl_models:
            applicable_acls.extend(acl.get_record_acls(invenio_record))
        if not applicable_acls:
            print('The record is not matched by any ACLs')
            return

        print('The following ACLs match the record:')
        for acl in applicable_acls:
            print('    %s with priority of %s' % (acl, acl.priority))
            for actor in acl.actors:
                print('        ', actor)
        print()

        matching_acls = list(current_explicit_acls.get_record_acls(invenio_record))

        print('Of these, the following ACLs will be used (have the highest priority):')
        for acl in matching_acls:
            print('    ', acl)
            for actor in acl.actors:
                print('        ', actor)

        print()

        print('The ACLs will get serialized to the following element')
        print(json.dumps({
            '_invenio_explicit_acls': current_explicit_acls.serialize_record_acls(matching_acls)
        }, indent=4))
