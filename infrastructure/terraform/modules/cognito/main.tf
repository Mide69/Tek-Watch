variable "name_prefix"                { type = string }
variable "environment"                { type = string }
variable "admin_google_client_id"     { type = string; default = "" }
variable "admin_google_client_secret" { type = string; default = ""; sensitive = true }

# ── Customer User Pool ────────────────────────────────────────────────────────

resource "aws_cognito_user_pool" "customers" {
  name = "${var.name_prefix}-customers"

  username_attributes      = ["preferred_username"]
  auto_verified_attributes = ["email"]

  username_configuration {
    case_sensitive = false
  }

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = false
    temporary_password_validity_days = 7
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    mutable             = true
    required            = false
    string_attribute_constraints {
      min_length = 0
      max_length = 256
    }
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
    invite_message_template {
      email_subject = "Your Tek Watch account"
      email_message = "Your Customer ID is {username} and temporary password is {####}"
      sms_message   = "Your Tek Watch temp password: {####}"
    }
  }

  tags = { Name = "${var.name_prefix}-customers" }
}

resource "aws_cognito_user_pool_client" "customers" {
  name         = "${var.name_prefix}-dashboard"
  user_pool_id = aws_cognito_user_pool.customers.id

  generate_secret                      = false
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  allowed_oauth_flows_user_pool_client = false

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH",
  ]

  access_token_validity  = 8    # hours
  id_token_validity      = 8
  refresh_token_validity = 30   # days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
}

# ── Admin User Pool ───────────────────────────────────────────────────────────

resource "aws_cognito_user_pool" "admins" {
  name = "${var.name_prefix}-admins"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 16
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 3
  }

  mfa_configuration = "ON"

  software_token_mfa_configuration {
    enabled = true
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  tags = { Name = "${var.name_prefix}-admins" }
}

resource "aws_cognito_user_pool_client" "admins" {
  name         = "${var.name_prefix}-admin-portal"
  user_pool_id = aws_cognito_user_pool.admins.id

  generate_secret                      = false
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  allowed_oauth_flows_user_pool_client = false

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH",
  ]

  access_token_validity  = 8
  id_token_validity      = 8
  refresh_token_validity = 1

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
}

output "customer_user_pool_id"   { value = aws_cognito_user_pool.customers.id }
output "customer_app_client_id"  { value = aws_cognito_user_pool_client.customers.id }
output "admin_user_pool_id"      { value = aws_cognito_user_pool.admins.id }
output "admin_app_client_id"     { value = aws_cognito_user_pool_client.admins.id }
