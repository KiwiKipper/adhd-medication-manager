# SNS: the backend publishes an alert here when a dose is logged late, and
# SNS fans it out to every confirmed subscriber. The backend doesn't know or
# care who is listening (pub/sub), so adding a second supporter is a new
# subscription, not a code change.

resource "aws_sns_topic" "alerts" {
  name = "${var.project}-alerts"
}

# Email subscriptions stay "PendingConfirmation" until the recipient clicks
# the link AWS sends (anti-spam opt-in). That click is a deliberate manual
# step; Terraform cannot do it.
resource "aws_sns_topic_subscription" "supporter_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

output "sns_topic_arn" {
  description = "Topic the backend publishes late-dose alerts to."
  value       = aws_sns_topic.alerts.arn
}
