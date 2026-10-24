variable "aws_region" {
  description = "AWS region used for this deployment."
  type        = string
  default     = "af-south-1"
}

variable "bucket_name" {
  description = "Globally unique name for the private, versioned data bucket."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.bucket_name)) && !strcontains(var.bucket_name, "..")
    error_message = "bucket_name must be a 3-63 character lowercase DNS-style name."
  }
}

variable "tags" {
  description = "Required ownership and cost-allocation tags."
  type        = map(string)
  default = {
    ManagedBy = "OpenTofu"
    Project   = "portfolio-infrastructure"
  }
  validation {
    condition     = contains(keys(var.tags), "Project") && contains(keys(var.tags), "ManagedBy")
    error_message = "tags must include Project and ManagedBy."
  }
}
