import axios from 'axios'


export async function getPlatforms () {
    return axios.get('/api/platforms')
}
