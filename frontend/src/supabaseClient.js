import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Supabase 환경 변수가 설정되지 않았습니다. .env 파일을 확인해 주세요.')
}

export const supabase = createClient(supabaseUrl || '', supabaseAnonKey || '')

export async function fetchNewsArticles({ market, query, limit, offset }) {
  let q = supabase
    .from('news_articles')
    .select('*', { count: 'exact' })
    .order('published_at', { ascending: false })
    .range(offset, offset + limit - 1)

  if (market && market !== 'ALL') {
    q = q.eq('market', market)
  }

  if (query) {
    q = q.or(
      `title.ilike.%${query}%,summary.ilike.%${query}%,company_name.ilike.%${query}%,symbol.ilike.%${query}%`
    )
  }

  const { data, count, error } = await q

  if (error) throw error

  return {
      items: data,
      totalCount: count || 0
  }
}
