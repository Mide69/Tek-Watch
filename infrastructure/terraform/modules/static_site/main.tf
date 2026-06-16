# Static site hosting (S3 + CloudFront + Origin Access Control) for one app.
# Instantiated twice from root main.tf — once for the dashboard, once for the
# admin portal. Both ship as Next.js static exports (output: 'export') synced
# to S3 by .github/workflows/{dashboard,admin-portal}.yml's deploy jobs, which
# expect the S3 bucket name and CloudFront distribution ID as GitHub secrets
# (see docs/GUIDE.md's secrets bootstrap table — those secrets are populated
# from this module's outputs via `terraform output`).

variable "name_prefix" { type = string }
variable "site_name" { type = string } # e.g. "dashboard" or "admin"
variable "environment" { type = string }
variable "domain_name" { type = string } # full FQDN, e.g. "app.tekwatch.io"

variable "certificate_arn" {
  description = "ACM cert ARN in us-east-1 for the custom domain. Empty string uses the CloudFront default *.cloudfront.net cert with no custom domain — lets this module stand up cleanly before a cert/DNS exist."
  type        = string
  default     = ""
}

locals {
  use_custom_domain = var.certificate_arn != ""
}

# ── S3 — origin bucket (private; CloudFront reaches it via OAC only) ─────────

resource "aws_s3_bucket" "site" {
  bucket = "${var.name_prefix}-${var.site_name}"
  # prod buckets require an explicit empty + destroy before terraform can
  # remove them — deliberate friction against accidental prod data loss.
  force_destroy = var.environment != "prod"

  tags = { Name = "${var.name_prefix}-${var.site_name}" }
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket                  = aws_s3_bucket.site.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "site" {
  bucket = aws_s3_bucket.site.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "site" {
  bucket = aws_s3_bucket.site.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ── CloudFront ─────────────────────────────────────────────────────────────

resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "${var.name_prefix}-${var.site_name}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  default_root_object = "index.html"
  comment             = "${var.name_prefix}-${var.site_name}"
  price_class         = "PriceClass_100" # US/EU/Canada — matches the eu-west-2-centric customer base
  aliases             = local.use_custom_domain ? [var.domain_name] : []

  origin {
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_id                = "s3-${var.site_name}"
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  default_cache_behavior {
    target_origin_id       = "s3-${var.site_name}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  # Next.js static export with trailingSlash:true pre-renders every route as
  # /<route>/index.html. A request for a path with no matching object (e.g. a
  # stale bookmark) would otherwise surface S3's raw access-denied response —
  # serve the SPA's actual 404 page instead.
  custom_error_response {
    error_code         = 403
    response_code      = 404
    response_page_path = "/404.html"
  }
  custom_error_response {
    error_code         = 404
    response_code      = 404
    response_page_path = "/404.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = !local.use_custom_domain
    acm_certificate_arn            = local.use_custom_domain ? var.certificate_arn : null
    ssl_support_method             = local.use_custom_domain ? "sni-only" : null
    minimum_protocol_version       = local.use_custom_domain ? "TLSv1.2_2021" : null
  }

  tags = { Name = "${var.name_prefix}-${var.site_name}" }
}

# ── Bucket policy — allow only this distribution to read via OAC ────────────

data "aws_iam_policy_document" "site" {
  statement {
    sid       = "AllowCloudFrontServicePrincipalReadOnly"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id
  policy = data.aws_iam_policy_document.site.json
}

output "bucket_name" { value = aws_s3_bucket.site.id }
output "cloudfront_distribution_id" { value = aws_cloudfront_distribution.site.id }
output "cloudfront_domain_name" { value = aws_cloudfront_distribution.site.domain_name }
