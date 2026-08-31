"""a171 Irrelevant Paint -- ignore salient border churn when allocating memory."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CORE,BORDER_A,BORDER_B,OBJECT_A,OBJECT_B,MEMORY,SELECTED,PREDICT,ERROR=7,8,12,14,10,13,9,11,4,6
BAD=15
LEVELS=[
 {"name":"Advance Core","seq":(1,)},{"name":"Select Feature","seq":(2,)},
 {"name":"Cycle Paint","seq":(3,1)},{"name":"Copy Causal State","seq":(1,2,3,4,2)},
 {"name":"Reject Nuisance","seq":(1,3,2,1,4,3,2)},{"name":"Irrelevant Paint","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 core,border,selected,cursor,prediction,errors,history,snapshot=s
 if a==1:core=(core+1)%6;border=(border+2)%8;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%4;selected^=1<<cursor;history=(history+(2,))[-8:]
 elif a==3:border=(border+1)%8;history=(history+(3,))[-8:]
 elif a==4:prediction=(core+1)%6 if (selected&0b0011) else border%6;errors=int(prediction!=(core+1)%6)+int(bool(selected&0b1100));history=(history+(4,))[-8:]
 elif a==5:snapshot=(core,border,selected,cursor,prediction,errors,history)
 return core,border,selected,cursor,prediction,errors,history,snapshot
for q in LEVELS:
 s=(0,0,0b0011,0,1,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[3:61,3:61]=BORDER_A if g.border%2==0 else BORDER_B;f[5:59,5:59]=BG;f[12:48,12:52]=CORE;f[20:40,18:31]=OBJECT_A;f[20:40,36:49]=OBJECT_B
  for i in range(4):x=10+i*12;f[51:57,x:x+9]=SELECTED if (g.selected>>i)&1 else MEMORY;f[48:51,x:x+9]=PREDICT if i==g.cursor else CORE
  f[7:10,8:8+g.prediction*7]=PREDICT;f[54:58,50:50+g.errors*3]=ERROR
  if g.bad:f[1:4,18:46]=BAD
  return f
class A171(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a171",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.core,self.border,self.selected,self.cursor,self.prediction,self.errors,self.history,self.snapshot=(0,0,0b0011,0,1,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.core,self.border,self.selected,self.cursor,self.prediction,self.errors,self.history,self.snapshot=advance((self.core,self.border,self.selected,self.cursor,self.prediction,self.errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.core,self.border,self.selected,self.cursor,self.prediction,self.errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
