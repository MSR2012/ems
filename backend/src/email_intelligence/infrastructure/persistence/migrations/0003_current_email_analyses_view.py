"""Published read model: the current analysis per email.

"Current" = the most recently analyzed COMPLETED row; if none has completed yet, the most
recent row (so PENDING/RUNNING/FAILED status is visible). A re-analysis under a new prompt or
model version becomes current as soon as it completes.
"""

from django.db import migrations

FORWARD = r"""
CREATE OR REPLACE VIEW current_email_analyses AS
SELECT DISTINCT ON (a.email_id)
    a.email_id, a.id AS analysis_id, a.user_id, a.status, a.priority, a.priority_confidence,
    a.spam_likelihood, a.reply_urgency, a.category, a.sentiment, a.model, a.prompt_version,
    a.analyzed_at, a.error
FROM email_analyses a
ORDER BY a.email_id, (a.status = 'COMPLETED') DESC, a.analyzed_at DESC NULLS LAST, a.id DESC;
"""

BACKWARD = "DROP VIEW IF EXISTS current_email_analyses;"


class Migration(migrations.Migration):
    dependencies = [("email_intelligence", "0002_initial")]
    operations = [migrations.RunSQL(FORWARD, BACKWARD)]
