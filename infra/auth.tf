# Cognito: the user directory behind F5 (spec 10.4). Passwords never touch Scrappy's
# database or its code — the `users` table stores only an opaque id.

resource "aws_cognito_user_pool" "users" {
  name = "scrappy-users"

  # People sign in with an email address; there is no separate username to remember.
  username_attributes = ["email"]

  # Cognito emails a six-digit code at sign-up, and the account doesn't work until it is
  # entered. Spec 10.4 originally called for a pre-sign-up Lambda that skipped this; the
  # developer chose real verification on October 28, 2026, so that trigger is not built.
  auto_verified_attributes = ["email"]

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "Your Scrappy verification code"
    email_message        = "Welcome to Scrappy. Your verification code is {####}."
  }

  # US-1: at least 8 characters, with a lowercase letter, an uppercase letter and a number.
  # Enforced here, server-side; the sign-up form mirrors it only so it can complain early.
  password_policy {
    minimum_length                   = 8
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = false
    temporary_password_validity_days = 7
  }

  # What makes "forgot password" work (US-16).
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # Cognito's own sender: free, and capped at 50 messages a day. A real product would move
  # to SES for volume and for sending from its own domain.
  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }
}

resource "aws_cognito_user_pool_client" "web" {
  name         = "scrappy-web"
  user_pool_id = aws_cognito_user_pool.users.id

  # A browser cannot keep a secret, and Amplify expects a public client.
  generate_secret = false

  # SRP proves the password without ever sending it. The flows that would accept a plain
  # password are deliberately absent, so they cannot be used even by mistake.
  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  # One hour of access, thirty days of refresh: US-2's "the session survives a refresh and
  # lasts up to 30 days".
  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # Stops a signed-in user from rewriting their own email or name through the client.
  read_attributes  = ["email", "email_verified"]
  write_attributes = ["email"]
}
