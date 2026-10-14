import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import api from "@/api/client";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";

type Document = {entity_type:string;id:number;number:string;date:string;status:string;url:string;can_archive:boolean;can_restore:boolean};
export default function PurchasingExceptionPanel({dateFrom,dateTo,businessUnitId}:{dateFrom:string;dateTo:string;businessUnitId?:number}) {
  const [open,setOpen]=useState(false);
  const [archived,setArchived]=useState(false);
  const client=useQueryClient();
  const query=useQuery({queryKey:["purchasing-exceptions",dateFrom,dateTo,archived,businessUnitId],queryFn:async()=>(await api.get<{items:Document[]}>("/purchasing-exceptions",{params:{business_unit_id:businessUnitId,date_from:dateFrom||undefined,date_to:dateTo||undefined,archived}})).data,enabled:open});
  const action=useMutation({mutationFn:async({document,reason}:{document:Document;reason:string})=>api.post(`/purchasing-exceptions/${document.entity_type}/${document.id}/${archived?"restore":"archive"}`,{reason}),onSuccess:()=>{client.invalidateQueries({queryKey:["purchasing-exceptions"]});client.invalidateQueries({queryKey:["purchasing-report"]});},onError:()=>toast.error("Unable to change document archive status. Check source dependencies and permission.")});
  const decide=(document:Document)=>{const reason=window.prompt(`${archived?"Restore":"Archive"} ${document.number}: reason`);if(reason?.trim() && reason.trim().length>=3) action.mutate({document,reason:reason.trim()});};
  return <div className="print:hidden"><Button variant="outline" onClick={()=>setOpen(value=>!value)} aria-expanded={open}>Closing documents / Archive</Button>{open && <Card className="mt-2 overflow-auto p-2"><div className="mb-2 flex gap-2"><Button variant={!archived?"primary":"outline"} onClick={()=>setArchived(false)}>Unfinished</Button><Button variant={archived?"primary":"outline"} onClick={()=>setArchived(true)}>Archive</Button></div>{query.isError?<p role="alert">Documents could not be loaded.</p>:<Table><THead><TR><TH>Document</TH><TH>Date</TH><TH>Status</TH><TH>Action</TH></TR></THead><TBody>{(query.data?.items??[]).map(document=><TR key={`${document.entity_type}-${document.id}`}><TD><Link className="text-blue-700 hover:underline" to={document.url}>{document.number}</Link></TD><TD>{document.date.slice(0,10)}</TD><TD>{document.status}</TD><TD>{(archived?document.can_restore:document.can_archive)&&<Button size="sm" variant="outline" disabled={action.isPending} onClick={()=>decide(document)}>{archived?"Restore":"Archive"}</Button>}</TD></TR>)}</TBody></Table>}</Card>}</div>;
}
