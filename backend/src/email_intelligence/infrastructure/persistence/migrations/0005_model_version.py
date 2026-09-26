"""Persist the concrete model version reported by the AI provider and expose it in the
published `current_email_analyses` read model."""

from django.db import migrations, models

VIEW = r"""
DROP VIEW IF EXISTS current_email_analyses;
CREATE VIEW current_email_analyses AS
SELECT DISTINCT ON (a.email_id)
    a.email_id, a.id AS analysis_id, a.user_id, a.status, a.priority, a.priority_confidence,
    a.spam_likelihood, a.reply_urgency, a.category, a.sentiment, a.model, a.model_version,
    a.prompt_version, a.analyzed_at, a.error,
    (SELECT b.status FROM email_analyses b WHERE b.email_id = a.email_id
      ORDER BY b.id DESC LIMIT 1) AS latest_status
FROM email_analyses a
ORDER BY a.email_id, (a.status = 'COMPLETED') DESC, a.analyzed_at DESC NULLS LAST, a.id DESC;
"""

OLD_VIEW = r"""
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


class Migration(migrations.Migration):
    dependencies = [("email_intelligence", "0004_view_latest_status")]
    operations = [
        migrations.RunSQL("DROP VIEW IF EXISTS current_email_analyses;", OLD_VIEW),
        migrations.AddField(
            model_name="emailanalysismodel", name="model_version",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.RunSQL(
            VIEW + "UPDATE email_analyses SET model_version = model "
                   "WHERE status = 'COMPLETED' AND model_version IS NULL;",
            "DROP VIEW IF EXISTS current_email_analyses;"),
    ]
