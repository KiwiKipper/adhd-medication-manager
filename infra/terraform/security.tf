# One security group per tier. Each tier only accepts traffic from the tier in
# front of it, and the rules name that tier's security group as the source
# rather than an IP range, so they keep working when instances are replaced
# and get new addresses.
#
#   internet --80--> frontend --8000--> backend --5432--> db
#   your IP --22--> frontend, backend

# Trust boundary 1: the internet reaches only the frontend, and only on HTTP.
resource "aws_security_group" "frontend" {
  name        = "${var.project}-frontend"
  description = "nginx + Vue SPA: HTTP from anywhere, SSH from the admin IP"
  vpc_id      = data.aws_vpc.default.id

  tags = { Name = "${var.project}-frontend" }
}

# Trust boundary 2: the API is reachable only from the frontend instance.
resource "aws_security_group" "backend" {
  name        = "${var.project}-backend"
  description = "Django API: port 8000 from the frontend SG only, SSH from the admin IP"
  vpc_id      = data.aws_vpc.default.id

  tags = { Name = "${var.project}-backend" }
}

# Trust boundary 3: the database is reachable only from the backend instance.
resource "aws_security_group" "db" {
  name        = "${var.project}-db"
  description = "RDS PostgreSQL: port 5432 from the backend SG only"
  vpc_id      = data.aws_vpc.default.id

  tags = { Name = "${var.project}-db" }
}

# --- frontend ---------------------------------------------------------------

resource "aws_vpc_security_group_ingress_rule" "frontend_http" {
  security_group_id = aws_security_group.frontend.id
  description       = "HTTP from the internet"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "frontend_ssh" {
  security_group_id = aws_security_group.frontend.id
  description       = "SSH from the admin IP"
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  cidr_ipv4         = var.my_ip
}

# --- backend ----------------------------------------------------------------

resource "aws_vpc_security_group_ingress_rule" "backend_api" {
  security_group_id            = aws_security_group.backend.id
  description                  = "Django API from the frontend instance"
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  referenced_security_group_id = aws_security_group.frontend.id
}

resource "aws_vpc_security_group_ingress_rule" "backend_ssh" {
  security_group_id = aws_security_group.backend.id
  description       = "SSH from the admin IP"
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  cidr_ipv4         = var.my_ip
}

# --- db ---------------------------------------------------------------------

resource "aws_vpc_security_group_ingress_rule" "db_postgres" {
  security_group_id            = aws_security_group.db.id
  description                  = "PostgreSQL from the backend instance"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.backend.id
}

# --- egress -----------------------------------------------------------------
# All outbound allowed: apt, git clone and npm on the instances, SNS from the
# backend. Only inbound is restricted.

resource "aws_vpc_security_group_egress_rule" "all" {
  for_each = {
    frontend = aws_security_group.frontend.id
    backend  = aws_security_group.backend.id
    db       = aws_security_group.db.id
  }

  security_group_id = each.value
  description       = "All outbound"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}
