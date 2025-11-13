import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import relativeTime from 'dayjs/plugin/relativeTime'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'

dayjs.locale('zh-cn')
dayjs.extend(relativeTime)
dayjs.extend(utc)
dayjs.extend(timezone)

export function formatDateTime(date, format = 'YYYY-MM-DD HH:mm:ss') {
  if (!date) return ''
  if (typeof date === 'string' && /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(date)) {
    return date
  }
  let d = dayjs(date)
  if (typeof date === 'string' && (date.endsWith('Z') || (!date.includes('+') && !date.includes('T')))) {
    d = dayjs.utc(date)
  }
  return d.tz('Asia/Shanghai').format(format)
}

export function formatDate(date, format = 'YYYY-MM-DD') {
  if (!date) return ''
  return dayjs(date).tz('Asia/Shanghai').format(format)
}

export function formatTime(date, format = 'HH:mm:ss') {
  if (!date) return ''
  return dayjs(date).tz('Asia/Shanghai').format(format)
}

export function getRelativeTime(date) {
  if (!date) return ''
  return dayjs(date).fromNow()
}

export function getTimeDiff(date1, date2, unit = 'day') {
  return dayjs(date1).diff(dayjs(date2), unit)
}

export function isExpired(date) {
  if (!date) return true
  return dayjs(date).isBefore(dayjs())
}

export function isExpiringSoon(date, days = 7) {
  if (!date) return false
  const expiryDate = dayjs(date)
  const now = dayjs()
  const diffDays = expiryDate.diff(now, 'day')
  return diffDays >= 0 && diffDays <= days
}

export function getRemainingDays(date) {
  if (!date) return 0
  const expiryDate = dayjs(date)
  const now = dayjs()
  const diffDays = expiryDate.diff(now, 'day')
  return Math.max(0, diffDays)
}

export function getRemainingTime(date) {
  if (!date) return { days: 0, hours: 0, minutes: 0, seconds: 0 }
  const expiryDate = dayjs(date)
  const now = dayjs()
  const diff = expiryDate.diff(now)
  if (diff <= 0) {
    return { days: 0, hours: 0, minutes: 0, seconds: 0 }
  }
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
  const seconds = Math.floor((diff % (1000 * 60)) / 1000)
  return { days, hours, minutes, seconds }
}

export function formatRemainingTime(date) {
  if (!date) return '已过期'
  const remaining = getRemainingTime(date)
  if (remaining.days > 0) {
    return `${remaining.days}天${remaining.hours}小时`
  } else if (remaining.hours > 0) {
    return `${remaining.hours}小时${remaining.minutes}分钟`
  } else if (remaining.minutes > 0) {
    return `${remaining.minutes}分钟${remaining.seconds}秒`
  } else if (remaining.seconds > 0) {
    return `${remaining.seconds}秒`
  } else {
    return '已过期'
  }
}

export function getMonthName(month) {
  const monthNames = [
    '一月', '二月', '三月', '四月', '五月', '六月',
    '七月', '八月', '九月', '十月', '十一月', '十二月'
  ]
  return monthNames[month - 1] || ''
}

export function getWeekdayName(day) {
  const weekdayNames = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  return weekdayNames[day] || ''
}

const checkDateSame = (date, unit) => {
  if (!date) return false
  return dayjs(date).isSame(dayjs(), unit)
}

export function isToday(date) {
  return checkDateSame(date, 'day')
}

export function isYesterday(date) {
  if (!date) return false
  return dayjs(date).isSame(dayjs().subtract(1, 'day'), 'day')
}

export function isThisWeek(date) {
  return checkDateSame(date, 'week')
}

export function isThisMonth(date) {
  return checkDateSame(date, 'month')
}

export function isThisYear(date) {
  return checkDateSame(date, 'year')
}

export function getDateRange(range) {
  const now = dayjs()
  switch (range) {
    case 'today':
      return {
        start: now.startOf('day'),
        end: now.endOf('day')
      }
    case 'yesterday':
      const yesterday = now.subtract(1, 'day')
      return {
        start: yesterday.startOf('day'),
        end: yesterday.endOf('day')
      }
    case 'week':
      return {
        start: now.startOf('week'),
        end: now.endOf('week')
      }
    case 'month':
      return {
        start: now.startOf('month'),
        end: now.endOf('month')
      }
    case 'year':
      return {
        start: now.startOf('year'),
        end: now.endOf('year')
      }
    default:
      return {
        start: now.startOf('day'),
        end: now.endOf('day')
      }
  }
}

export function formatDuration(seconds) {
  if (!seconds || seconds < 0) return '0秒'
  const days = Math.floor(seconds / (24 * 60 * 60))
  const hours = Math.floor((seconds % (24 * 60 * 60)) / (60 * 60))
  const minutes = Math.floor((seconds % (60 * 60)) / 60)
  const secs = seconds % 60
  let result = ''
  if (days > 0) result += `${days}天`
  if (hours > 0) result += `${hours}小时`
  if (minutes > 0) result += `${minutes}分钟`
  if (secs > 0 || result === '') result += `${secs}秒`
  return result
}

export function getCurrentTimestamp() {
  return dayjs().valueOf()
}

export function timestampToDate(timestamp) {
  return dayjs(timestamp).toDate()
}

export function dateToTimestamp(date) {
  return dayjs(date).valueOf()
}

export function setTimezone(timezone = 'Asia/Shanghai') {
  dayjs.tz.setDefault(timezone)
}

export function getTimezoneTime(date, timezone = 'Asia/Shanghai') {
  return dayjs(date).tz(timezone)
}

setTimezone()

export default {
  formatDateTime,
  formatDate,
  formatTime,
  getRelativeTime,
  getTimeDiff,
  isExpired,
  isExpiringSoon,
  getRemainingDays,
  getRemainingTime,
  formatRemainingTime,
  getMonthName,
  getWeekdayName,
  isToday,
  isYesterday,
  isThisWeek,
  isThisMonth,
  isThisYear,
  getDateRange,
  formatDuration,
  getCurrentTimestamp,
  timestampToDate,
  dateToTimestamp,
  setTimezone,
  getTimezoneTime
}
