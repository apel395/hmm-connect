import Input from "@/components/ui/Input";

export default function SearchBox({

value,

onChange,

}:any){

return(

<Input

placeholder="Search..."

value={value}

onChange={e=>

onChange(

e.target.value,

)

}

/>

);

}
