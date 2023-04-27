import axios from 'axios'


export async function fetchPlatforms () {
    return axios.get('/api/platforms')
}
