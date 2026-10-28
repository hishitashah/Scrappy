# Lets GitHub Actions deploy into this account without storing an AWS key anywhere
# (spec 10.7). GitHub presents a short-lived OIDC token per workflow run; AWS trades it for
# credentials that expire in minutes.

# AWS has validated GitHub's certificate against its own trust store since July 2023, so no
# thumbprint is pinned here. The field is left unset rather than empty on purpose: AWS fills
# one in itself, and an explicit [] makes Terraform try to clear it on every apply.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "github_deploy_assume_role" {
  statement {
    # TagSession is required as well as the assume itself: configure-aws-credentials
    # attaches session tags (repo, workflow, actor, branch) by default, and STS refuses the
    # whole call without this action — reporting it, confusingly, as "Not authorized to
    # perform sts:AssumeRoleWithWebIdentity". The tags are worth keeping: they identify in
    # CloudTrail which workflow run made each change.
    actions = ["sts:AssumeRoleWithWebIdentity", "sts:TagSession"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # The security model in one line: only a workflow running on main, in this repository,
    # can assume this role. A pull request — including one from a fork — gets nothing.
    #
    # Both forms of the subject claim are listed because GitHub sends the second one here.
    # The documented format is `repo:OWNER/REPO:ref:...`, but this repository receives the
    # newer immutable-identifier format, `repo:OWNER@ownerID/REPO@repoID:ref:...` — verified
    # in CloudTrail on October 28, 2026, after the documented form failed with an opaque
    # AccessDenied. Listing both means the role keeps working whichever GitHub sends.
    #
    # Case matters too: the repository is "Scrappy", not "scrappy". IAM compares literally.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:hishitashah/Scrappy:ref:refs/heads/main",
        "repo:hishitashah@149904682/Scrappy@1376527431:ref:refs/heads/main",
      ]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name               = "scrappy-github-deploy"
  description        = "Assumed by GitHub Actions on pushes to main"
  assume_role_policy = data.aws_iam_policy_document.github_deploy_assume_role.json
}

# Broad permissions, narrow trust: the role can do anything, but almost nothing can assume
# it. Least privilege here is post-MVP item 5 — a deliberate shortcut, not an oversight.
resource "aws_iam_role_policy_attachment" "github_deploy_admin" {
  role       = aws_iam_role.github_deploy.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
