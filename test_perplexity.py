#!/usr/bin/env python3
"""Tests for perplexity.py"""

import unittest
from unittest.mock import patch, MagicMock
import argparse
import os
import io
import sys

from perplexity import (
    ModelValidator,
    ApiKeyValidator,
    Perplexity,
    ApiKeyNotFoundException,
    InvalidSelectedModelException,
    display,
    AVAILABLE_MODELS,
)


class TestModelValidator(unittest.TestCase):
    """Tests for ModelValidator class"""

    def test_validate_valid_models(self):
        """Test that all available models are valid"""
        for model in AVAILABLE_MODELS:
            self.assertTrue(ModelValidator.validate(model))

    def test_validate_invalid_model(self):
        """Test that invalid models are rejected"""
        self.assertFalse(ModelValidator.validate("invalid-model"))
        self.assertFalse(ModelValidator.validate(""))
        self.assertFalse(ModelValidator.validate("gpt-4"))

    def test_get_available_models(self):
        """Test that get_AVAILABLE_MODELS returns the correct list"""
        models = ModelValidator.get_AVAILABLE_MODELS()
        self.assertEqual(models, AVAILABLE_MODELS)
        self.assertIn("sonar-pro", models)


class TestApiKeyValidator(unittest.TestCase):
    """Tests for ApiKeyValidator class"""

    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-api-key"})
    def test_get_api_key_from_system_exists(self):
        """Test getting API key when it exists"""
        api_key = ApiKeyValidator.get_api_key_from_system()
        self.assertEqual(api_key, "test-api-key")

    @patch.dict(os.environ, {}, clear=True)
    def test_get_api_key_from_system_not_exists(self):
        """Test getting API key when it doesn't exist"""
        # Remove the key if it exists
        os.environ.pop("PERPLEXITY_API_KEY", None)
        api_key = ApiKeyValidator.get_api_key_from_system()
        self.assertIsNone(api_key)


class TestPerplexityInit(unittest.TestCase):
    """Tests for Perplexity class initialization"""

    def create_args(self, model="sonar-pro", api_key=None, usage=False, citations=False, glow=False):
        """Helper to create args namespace"""
        return argparse.Namespace(
            model=model,
            api_key=api_key,
            usage=usage,
            citations=citations,
            glow=glow
        )

    def test_invalid_model_raises_exception(self):
        """Test that invalid model raises InvalidSelectedModelException"""
        args = self.create_args(model="invalid-model", api_key="test-key")
        with self.assertRaises(InvalidSelectedModelException):
            Perplexity(args)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_api_key_raises_exception(self):
        """Test that missing API key raises ApiKeyNotFoundException"""
        os.environ.pop("PERPLEXITY_API_KEY", None)
        args = self.create_args(api_key=None)
        with self.assertRaises(ApiKeyNotFoundException):
            Perplexity(args)

    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "env-api-key"})
    def test_api_key_from_env(self):
        """Test that API key is read from environment"""
        args = self.create_args(api_key=None)
        perplexity = Perplexity(args)
        self.assertEqual(perplexity.setup.api_key, "env-api-key")

    def test_api_key_from_args(self):
        """Test that API key from args takes precedence"""
        args = self.create_args(api_key="arg-api-key")
        perplexity = Perplexity(args)
        self.assertEqual(perplexity.setup.api_key, "arg-api-key")


class TestPerplexityGetResponse(unittest.TestCase):
    """Tests for Perplexity.get_response method"""

    def create_perplexity_instance(self):
        """Helper to create a Perplexity instance"""
        args = argparse.Namespace(
            model="sonar-pro",
            api_key="test-api-key",
            usage=False,
            citations=False,
            glow=False
        )
        return Perplexity(args)

    @patch('perplexity.requests.post')
    def test_request_has_timeout(self, mock_post):
        """Test that requests are made with a timeout (security fix)"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}],
            "citations": [],
            "usage": {}
        }
        mock_post.return_value = mock_response

        perplexity = self.create_perplexity_instance()
        perplexity.get_response("test query")

        # Verify timeout was passed to requests.post
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        self.assertIn('timeout', call_kwargs)
        self.assertEqual(call_kwargs['timeout'], 30)

    @patch('perplexity.requests.post')
    def test_authorization_header_format(self, mock_post):
        """Test that Authorization header uses Bearer token"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}],
            "citations": [],
            "usage": {}
        }
        mock_post.return_value = mock_response

        perplexity = self.create_perplexity_instance()
        perplexity.get_response("test query")

        call_kwargs = mock_post.call_args[1]
        headers = call_kwargs['headers']
        self.assertIn('Authorization', headers)
        self.assertTrue(headers['Authorization'].startswith('Bearer '))


class TestDisplay(unittest.TestCase):
    """Tests for display function"""

    def test_display_output(self):
        """Test that display produces output"""
        captured_output = io.StringIO()
        sys.stdout = captured_output
        display("Test message", "white", False, "black")
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        self.assertIn("Test message", output)


class TestSecurityNoSensitiveDataInLogs(unittest.TestCase):
    """Security tests to ensure sensitive data is not logged"""

    @patch('perplexity.logger')
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "secret-api-key-12345"})
    def test_api_key_not_logged_on_init(self, mock_logger):
        """Test that API key value is not logged during initialization"""
        args = argparse.Namespace(
            model="sonar-pro",
            api_key=None,
            usage=False,
            citations=False,
            glow=False
        )
        Perplexity(args)

        # Check all debug calls don't contain the actual API key
        for call in mock_logger.debug.call_args_list:
            call_str = str(call)
            self.assertNotIn("secret-api-key-12345", call_str)


if __name__ == "__main__":
    unittest.main()
