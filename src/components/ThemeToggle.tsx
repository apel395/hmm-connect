import Button from "@/components/ui/Button";

import{

useTheme,

}from"@/theme/ThemeProvider";

export default function ThemeToggle(){

const{

theme,

setTheme,

}=useTheme();

return(

<Button

variant="outline"

onClick={()=>

setTheme(

theme==="light"

?

"dark"

:

"light",

)

}

>

{

theme==="light"

?

"🌙"

:

"☀️"

}

</Button>

);

}
