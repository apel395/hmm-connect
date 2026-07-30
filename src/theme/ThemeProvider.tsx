import{

createContext,
useContext,
useEffect,
useState,

}from"react";

const ThemeContext=

createContext<any>(null);

export function ThemeProvider({

children,

}:any){

const[theme,setTheme]=

useState(

localStorage.getItem("theme")||

"light",

);

useEffect(()=>{

document.documentElement.className=

theme;

localStorage.setItem(

"theme",

theme,

);

},[theme]);

return(

<ThemeContext.Provider

value={{

theme,

setTheme,

}}

>

{children}

</ThemeContext.Provider>

);

}

// The context hook intentionally shares this module with its provider.
// eslint-disable-next-line react-refresh/only-export-components
export function useTheme(){

return useContext(

ThemeContext,

);

}
