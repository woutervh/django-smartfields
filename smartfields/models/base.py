from django.db import models

class Model(models.Model):

    smartfields_managers = []

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(Model, self).__init__(*args, **kwargs)
        for manager in self.smartfields_managers:
            manager.handle(self)

    def save(self, *args, **kwargs):
        for manager in self.smartfields_managers:
            manager.handle(self)
        super(Model, self).save(*args, **kwargs)

    def smartfield_status(self, field_name):
        """A way to find out a status a filed."""
        field = self._meta.get_field(field_name)
        return field.get_status(self)