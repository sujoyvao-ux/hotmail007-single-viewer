const express = require('express');
const cors = require('cors');
const axios = require('axios');
const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

app.get('/api/mail', async (req, res) => {
    const { clientKey, account, folder, start_timestamp } = req.query;

    if (!clientKey || !account || !folder) {
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

        const response = await axios.get(url, { params, timeout: 30000 });
        
        res.json({
            success: response.data.success || false,
            data: response.data.data || null,
            message: response.data.message || '',
            code: response.data.code || 0
        });
    } catch (error) {
        console.error('API Error:', error.message);
        res.status(500).json({
            success: false,
            message: error.response?.data?.message || error.message || 'API request failed',
            data: null
        });
    }
});

app.get('/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.listen(PORT, () => {
    console.log(`🚀 Server running on port ${PORT}`);
});