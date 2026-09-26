"""Add `latest_status` (status of the newest analysis row, e.g. a pending re-analysis) to the
published `current_email_analyses` read model."""

from django.db import migrations

FORWARD = r"""
DROP VIEW IF EXISTS current_email_analyses;
CREATE VIEW current_email_analyses AS
SELECT DISTINCT ON (a.email_id)
    a.email_id, a.id AS analysis_id, a.user_id, a.status, a.priority, a.priority_confidence,
    a.spam_likelihood, a.reply_urgency, a.category, a.sentiment, a.model, a.prompt_version,
    a.analyzed_at, a.error,
    (SELECT b.status FROM email_analyses b WHERE b.email_id = a.email_id
      ORDER BY b.id DESC LIMIT 1) AS latest_status
FROM email_analyses a
ORDER BY a.email_id, (a.status = 'COMPLETED') DESC, a.analyzed_at DESC NULLS LAST, a.id DESC;
"""

BACKWARD = r"""
DROP VIEW IF EXISTS current_email_analyses;
CREATE VIEW current_email_analyses AS
SELECT DISTINCT ON (a.email_id)
    a.email_id, a.id AS analysis_id, a.user_id, a.status, a.priority, a.priority_confidence,
    a.spam_likelihood, a.reply_urgency, a.category, a.sentiment, a.model, a.prompt_version,
    a.analyzed_at, a.error
FROM email_analyses a
ORDER BY a.email_id, (a.status = 'COMPLETED') DESC, a.analyzed_at DESC NULLS LAST, a.id DESC;
"""


class Migration(migrations.Migration):
    dependencies = [("email_intelligence", "0003_current_email_analyses_view")]
    operations = [migrations.RunSQL(FORWARD, BACKWARD)]
