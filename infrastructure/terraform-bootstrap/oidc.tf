# ── GitHub Actions OIDC provider ──────────────────────────────────────────────
# One per AWS account. Lets AWS trust ID tokens minted by GitHub's own OIDC
# issuer for THIS specific repo, instead of long-lived access-key secrets.

resource "aws_iam_openid_connect_provider" "github_actions" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # GitHub's well-known OIDC thumbprint. AWS now also verifies the provider's
  # TLS chain against its own trusted root CAs regardless of this value, but
  # the argument is still required by the resource schema.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

# ── IAM role GitHub Actions assumes ───────────────────────────────────────────
# Trust is scoped to this exact repo via the `sub` claim — no other GitHub
# repo, fork, or org can assume this role even though the OIDC provider
# itself is account-wide. `*` after the repo name allows any branch, tag, or
# environment within it (matches how the existing workflows already branch
# on dev/staging/prod via `if:` conditions rather than separate trust rules).

data "aws_iam_policy_document" "github_actions_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_org}/${var.github_repo}:*"]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "tek-watch-github-actions"
  assume_role_policy = data.aws_iam_policy_document.github_actions_trust.json
}

# Matches the same access level your SSO AdministratorAccess permission set
# already has — this role drives both app deploys (ECR/ECS/S3/CloudFront)
# AND `terraform apply` itself (terraform.yml uses the same AWS_ROLE_ARN
# secret), so it genuinely needs broad permissions across many resource
# types. The OIDC trust condition above is what keeps this safe: only
# workflow runs from this exact repo can assume it at all. Tighten to a
# scoped policy later if you want defense-in-depth beyond the repo-scoped
# trust condition.
resource "aws_iam_role_policy_attachment" "github_actions_admin" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

output "github_actions_role_arn" {
  description = "Set this as the AWS_ROLE_ARN secret in GitHub (repo or environment level)"
  value       = aws_iam_role.github_actions.arn
}
