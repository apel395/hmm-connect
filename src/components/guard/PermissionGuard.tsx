import { Navigate } from "react-router-dom";

export default function PermissionGuard({

allow,

children,

}:any){

if(!allow){

return<Navigate to="/403" replace/>;

}

return children;

}
