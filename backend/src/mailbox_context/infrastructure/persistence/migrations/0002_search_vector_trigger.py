"""Keep emails.search_vector up to date (sender, subject, body) with a PostgreSQL trigger."""

from django.db import migrations

FORWARD = r"""
CREATE OR REPLACE FUNCTION emails_search_vector_update() RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
      setweight(to_tsvector('simple',
          coalesce(NEW.sender_name, '') || ' ' || coalesce(NEW.sender_email, '') || ' ' ||
          translate(coalesce(NEW.sender_email, ''), '@._-+', '     ')), 'A')
   || setweight(to_tsvector('english', coalesce(NEW.subject, '')), 'B')
   || setweight(to_tsvector('english', left(coalesce(NEW.body_text, ''), 200000)), 'C');
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS emails_search_vector_trg ON emails;
CREATE TRIGGER emails_search_vector_trg
  BEFORE INSERT OR UPDATE OF sender_name, sender_email, subject, body_text ON emails
  FOR EACH ROW EXECUTE FUNCTION emails_search_vector_update();

UPDATE emails SET subject = subject;
"""

BACKWARD = r"""
DROP TRIGGER IF EXISTS emails_search_vector_trg ON emails;
DROP FUNCTION IF EXISTS emails_search_vector_update();
"""


class Migration(migrations.Migration):
    dependencies = [("mailbox", "0001_initial")]
    operations = [migrations.RunSQL(FORWARD, BACKWARD)]
