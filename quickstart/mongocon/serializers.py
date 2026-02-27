from rest_framework import serializers
from .models import Bot2, Bot

'''class Bot2Serializer(serializers.ModelSerializer):
    class Meta:
        model = Bot2
        fields = '__all__'

    def clean_data(self, data):
        print("[DEBUG] Incoming validated_data to clean_data:", data)
        # Remove keys with None, empty string, empty list, or empty dict
        cleaned = {k: v for k, v in data.items() if v not in [None, '', [], {}]}
        print("[DEBUG] Cleaned data:", cleaned)
        return cleaned

    def update(self, instance, validated_data):
        print("[DEBUG] In update() with validated_data:", validated_data)
        cleaned_data = self.clean_data(validated_data)
        print("[DEBUG] Passing cleaned_data to super().update():", cleaned_data)
        return super().update(instance, cleaned_data)

    def create(self, validated_data):
        print("[DEBUG] In create() with validated_data:", validated_data)
        cleaned_data = self.clean_data(validated_data)
        print("[DEBUG] Passing cleaned_data to super().create():", cleaned_data)
        return super().create(cleaned_data)


from .models import Bot


class BotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bot
        fields = '__all__'

    def clean_data(self, data):
        # Remove keys with None, empty string, empty list, or empty dict
        cleaned = {k: v for k, v in data.items() if v not in [None, '', [], {}]}
        return cleaned

    def update(self, instance, validated_data):
        cleaned_data = self.clean_data(validated_data)
        return super().update(instance, cleaned_data)

    def create(self, validated_data):
        cleaned_data = self.clean_data(validated_data)
        print("[DEBUG] Cleaned data in BotSerializer.create():", cleaned_data)
        return super().create(cleaned_data)
'''

class BotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bot
        fields = '__all__'
    # No overrides needed anymore!

class Bot2Serializer(serializers.ModelSerializer):
    class Meta:
        model = Bot2
        fields = '__all__'
    # No overrides needed anymore!