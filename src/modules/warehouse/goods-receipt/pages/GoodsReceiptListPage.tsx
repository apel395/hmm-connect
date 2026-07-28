import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import PageHeader from "@/components/common/PageHeader";

import GoodsReceiptTable from "../components/GoodsReceiptTable";

import{

useGoodsReceipts,

}from"../hooks/useGoodsReceipts";

export default function GoodsReceiptListPage(){

const{

data=[],

isLoading,

}=useGoodsReceipts();

return(

<div className="space-y-6">

<PageHeader

title="Goods Receipt"

description="Receive goods from suppliers"

/>

<Card>

{

isLoading

?

<Loading/>

:

<GoodsReceiptTable

rows={data}

/>

}

</Card>

</div>

);

}
