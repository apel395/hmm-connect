import Dialog, {
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/Dialog";

import Button from "@/components/ui/Button";


interface ConfirmDialogProps {

  open: boolean;

  title?: string;

  message: string;

  confirmText?: string;

  cancelText?: string;

  loading?: boolean;

  onConfirm: () => void;

  onClose: () => void;

}



export default function ConfirmDialog({

  open,

  title = "Confirm Action",

  message,

  confirmText = "Confirm",

  cancelText = "Cancel",

  loading = false,

  onConfirm,

  onClose,

}: ConfirmDialogProps) {


  return (

    <Dialog

      open={open}

      onOpenChange={(value) => {

        if (!value) {

          onClose();

        }

      }}

    >


      <DialogContent>


        <DialogHeader>

          <DialogTitle>

            {title}

          </DialogTitle>

        </DialogHeader>



        <DialogBody>

          <p className="text-sm text-slate-600">

            {message}

          </p>

        </DialogBody>



        <DialogFooter>


          <Button

            variant="outline"

            onClick={onClose}

            disabled={loading}

          >

            {cancelText}

          </Button>



          <Button

            onClick={onConfirm}

            disabled={loading}

          >

            {
              loading
                ? "Processing..."
                : confirmText
            }

          </Button>


        </DialogFooter>


      </DialogContent>


    </Dialog>

  );

}