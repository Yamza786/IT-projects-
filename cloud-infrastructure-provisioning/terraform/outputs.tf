output "bucket_name" {
  description = "Name of the private, versioned bucket."
  value       = aws_s3_bucket.portfolio_data.id
}

output "bucket_arn" {
  description = "ARN for IAM policy scoping."
  value       = aws_s3_bucket.portfolio_data.arn
}
