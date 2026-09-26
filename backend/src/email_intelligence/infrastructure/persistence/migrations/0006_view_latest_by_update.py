"""`latest_status` = status of the most recently *updated* analysis row, so a re-run of an older
row (e.g. the bulk "Analyze" button with force) is visible as in progress."""

from django.db import migrations

VIEW = r"""
DROP VIEW IF EXISTS current_email_analyses;
CREATE VIEW current_email_analyses AS
SELECT DISTINCT ON (a.email_id)
    a.email_id, a.id AS analysis_id, a.user_id, a.status, a.priority, a.priority_confidence,
    a.spam_likelihood, a.reply_urgency, a.category, a.sentiment, a.model, a.model_version,
    a.prompt_version, a.analyzed_at, a.error,
    (SELECT b.status FROM email_analyses b WHERE b.email_id = a.email_id
      ORDER BY b.updated_at DESC, b.id DESC LIMIT 1) AS latest_status
FROM email_analyses a
ORDER BY a.email_id, (a.status = 'COMPLETED') DESC, a.analyzed_at DESC NULLS LAST, a.id DESC;
"""

OLD = VIEW.replace("ORDER BY b.updated_at DESC, b.id DESC", "ORDER BY b.id DESC")


class Migration(migrations.Migration):
    dependencies = [("email_intelligence", "0005_model_version")]
    operations = [migrations.RunSQL(VIEW, OLD)]
