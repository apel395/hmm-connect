export const todayLocal = () => {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 10);
};

export const nowLocal = () => {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
};

export const isBeforeToday = (value?: string | null) => Boolean(value && value.slice(0, 10) < todayLocal());

export const isBeforeNow = (value?: string | null) => Boolean(value && value < nowLocal());

export const isBeforeDate = (value?: string | null, minimum?: string | null) => Boolean(value && minimum && value.slice(0, 10) < minimum.slice(0, 10));
