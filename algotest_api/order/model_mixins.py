from django.db import models


class CreatedAtModelMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class LastUpdatedAtModelMixin(models.Model):
    last_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
