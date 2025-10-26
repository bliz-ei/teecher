#!/bin/bash

# SSL Certificate Setup Script for iPhone Camera Access

echo "🔐 Setting up SSL certificates for HTTPS..."
echo ""

# Check if mkcert is installed
if ! command -v mkcert &> /dev/null; then
    echo "📦 Installing mkcert..."
    
    # Check OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install mkcert
            brew install nss # for Firefox support
        else
            echo "❌ Homebrew not found. Please install Homebrew first:"
            echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        sudo apt-get update
        sudo apt-get install -y mkcert
    else
        echo "❌ Unsupported OS. Please install mkcert manually from https://github.com/FiloSottile/mkcert"
        exit 1
    fi
fi

# Install local CA
echo "📜 Installing local Certificate Authority..."
mkcert -install

# Get local IP address
if [[ "$OSTYPE" == "darwin"* ]]; then
    LOCAL_IP=$(ipconfig getifaddr en0)
    if [ -z "$LOCAL_IP" ]; then
        LOCAL_IP=$(ipconfig getifaddr en1)
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    LOCAL_IP=$(hostname -I | awk '{print $1}')
fi

if [ -z "$LOCAL_IP" ]; then
    echo "⚠️  Could not detect local IP address automatically."
    echo "Please enter your local IP address (e.g., 192.168.1.221):"
    read LOCAL_IP
fi

echo ""
echo "📍 Your local IP: $LOCAL_IP"
echo ""

# Generate certificates
echo "🔑 Generating SSL certificates..."
mkcert -cert-file cert.pem -key-file key.pem localhost 127.0.0.1 ::1 $LOCAL_IP

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SSL certificates generated successfully!"
    echo ""
    echo "📋 Files created:"
    echo "   • cert.pem (SSL certificate)"
    echo "   • key.pem (private key)"
    echo ""
    echo "🚀 Next steps:"
    echo "   1. Run: python app.py"
    echo "   2. On iPhone Safari, go to: https://$LOCAL_IP:5001"
    echo "   3. Accept the security warning (your certificate is trusted)"
    echo ""
    echo "⚠️  iPhone Setup:"
    echo "   If you see 'This Connection Is Not Private':"
    echo "   1. Tap 'Show Details'"
    echo "   2. Tap 'Visit this website'"
    echo "   3. Tap 'Visit Website' again"
    echo ""
    echo "   OR install the CA certificate on your iPhone:"
    echo "   1. Find the rootCA.pem in: \$(mkcert -CAROOT)"
    echo "   2. AirDrop it to your iPhone"
    echo "   3. Settings → General → VPN & Device Management"
    echo "   4. Install the profile"
    echo "   5. Settings → General → About → Certificate Trust Settings"
    echo "   6. Enable full trust for the certificate"
    echo ""
else
    echo "❌ Failed to generate certificates"
    exit 1
fi