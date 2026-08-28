const express = require('express');
const cors = require('cors');
const axios = require('axios');
const path = require('path');
const app = express();
const PORT = process.env.PORT || 3000;

// Enable CORS for all routes
app.use(cors());
app.use(express.json());

// Serve static files from 'public' directory
app.use(express.static(path.join(__dirname, 'public')));

// Log all requests (for debugging)
app.use((req, res, next) => {
    console.log(`${req.method} ${req.url}`);
    next();
});

// API endpoint - Get latest mail
app.get('/api/mail', async (req, res) => {
    console.log('📨 API called with params:', req.query);
    
    const { clientKey, account, folder, start_timestamp } = req.query;

    if (!clientKey || !account || !folder) {
        console.log('❌ Missing parameters');
        return res.status(400).json({
            success: false,
            message: 'Missing required: clientKey, account, folder'
        });
    }

    try {
        const url = 'https://gapi.hotmail007.com/open/mail/latest';
        const params = {
            clientKey,
            account,
            folder,
            ...(start_timestamp && { start_timestamp })
        };

        console.log('🔄 Calling Hotmail007 API...');
        const response = await axios.get(url, { params, timeout: 30000 });
        
        console.log('✅ API Response received');
        
        res.json({
            success: response.data.success || false,
            data: response.data.data || null,
            message: response.data.message || '',
            code: response.data.code || 0
        });
    } catch (error) {
        console.error('❌ API Error:', error.message);
        if (error.response) {
            console.error('Response data:', error.response.data);
        }
        res.status(500).json({
            success: false,
            message: error.response?.data?.message || error.message || 'API request failed',
            data: null
        });
    }
});

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({ 
        status: 'ok', 
        timestamp: new Date().toISOString(),
        uptime: process.uptime()
    });
});

// Catch-all route - serve index.html for any other GET request
app.get('*', (req, res) => {
    console.log('📄 Serving index.html for:', req.url);
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Start server
app.listen(PORT, () => {
    console.log(`🚀 Server running on port ${PORT}`);
    console.log(`📁 Serving static files from: ${path.join(__dirname, 'public')}`);
    console.log(`🌐 Open: http://localhost:${PORT}`);
});
