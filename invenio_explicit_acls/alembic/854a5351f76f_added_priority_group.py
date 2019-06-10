#
# This file is part of Invenio.
# Copyright (C) 2016-2018 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Added priority_group."""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '854a5351f76f'
down_revision = '5ba4aa9a23ba'
branch_labels = ()
depends_on = None


def upgrade():
    """Upgrade database."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('explicit_acls_acl', sa.Column('priority_group', sa.String(length=32), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    """Downgrade database."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('explicit_acls_acl', 'priority_group')
    # ### end Alembic commands ###
