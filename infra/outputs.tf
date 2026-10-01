output "site_url" {
  description = "The public URL of the deployed frontend."
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "frontend_bucket" {
  description = "Bucket the built frontend is uploaded to."
  value       = aws_s3_bucket.frontend.id
}

output "cloudfront_distribution_id" {
  description = "Needed to invalidate the cache after a deploy."
  value       = aws_cloudfront_distribution.frontend.id
}
