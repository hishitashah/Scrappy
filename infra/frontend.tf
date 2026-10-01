# The frontend: a private S3 bucket holding the built React files, served through
# CloudFront (spec 10.7). The bucket is never public; CloudFront is the only reader.

locals {
  frontend_bucket = "scrappy-frontend-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket" "frontend" {
  bucket = local.frontend_bucket
}

# No website hosting, no public objects: everything goes through CloudFront, which is what
# gives us HTTPS and a free tier of 1 TB a month.
resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Origin Access Control lets this one distribution read the bucket, and nothing else can.
resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "scrappy-frontend"
  description                       = "Lets the Scrappy distribution read the frontend bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# AWS-managed CachingOptimized policy: long caching, gzip/brotli, no cookies forwarded.
data "aws_cloudfront_cache_policy" "caching_optimized" {
  name = "Managed-CachingOptimized"
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  comment             = "Scrappy frontend"
  default_root_object = "index.html"

  # North America and Europe only: the cheapest price class, and where the audience is.
  price_class = "PriceClass_100"

  origin {
    origin_id                = "frontend-bucket"
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  default_cache_behavior {
    target_origin_id       = "frontend-bucket"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.caching_optimized.id
    compress               = true
  }

  # React Router owns the URLs, but S3 has no object at /recipes/42/ingredients and answers
  # 403. Rewriting both 403 and 404 to index.html with a 200 is what lets a deep link be
  # opened or refreshed directly (spec 10.7).
  dynamic "custom_error_response" {
    for_each = [403, 404]

    content {
      error_code            = custom_error_response.value
      response_code         = 200
      response_page_path    = "/index.html"
      error_caching_min_ttl = 0
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # The default *.cloudfront.net certificate: free, and no custom domain is in scope.
  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# The bucket policy is written after the distribution exists, so it can name it exactly:
# only this distribution may read, and only via CloudFront.
resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = data.aws_iam_policy_document.frontend.json
}

data "aws_iam_policy_document" "frontend" {
  statement {
    sid       = "AllowCloudFrontRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.frontend.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.frontend.arn]
    }
  }
}
