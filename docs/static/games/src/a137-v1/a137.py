"""a137 Undo Group -- compose inferred inverses in reverse algebraic order."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,WORKSHOP,OBJECT,ORIGIN,OP_A,OP_B,INVERSE,CURSOR,RESTORED,ERROR=3,8,12,7,10,14,13,11,4,6
BAD=15
LEVELS=[
 {"name":"Apply Machine","seq":(1,)},{"name":"Select Object","seq":(2,)},
 {"name":"Invert Control","seq":(3,1)},{"name":"Reverse Order","seq":(1,2,3,4,2)},
 {"name":"Restore Origins","seq":(1,3,2,1,4,3,2)},{"name":"Undo Group","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 states,cursor,inverse,restored,order_error,history,snapshot=s;st=list(states)
 if a==1:st[cursor]=(st[cursor]+(-1 if inverse else 1))%8;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%5;history=(history+(2,))[-8:]
 elif a==3:inverse=1-inverse;history=(history+(3,))[-8:]
 elif a==4:restored=sum(int(x==0) for x in st);order_error=sum(min(x,8-x) for x in st);history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(st),cursor,inverse,restored,order_error,history)
 return tuple(st),cursor,inverse,restored,order_error,history,snapshot
for q in LEVELS:
 s=((1,2,3,4,5),0,0,0,15,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WORKSHOP
  for i,v in enumerate(g.states):
   x=8+i*10;f[15:49,x:x+8]=ORIGIN;h=4+v*3;f[45-h:45,x+1:x+7]=OBJECT;f[10:13,x:x+8]=INVERSE if g.inverse else OP_A if i%2==0 else OP_B
   if i==g.cursor:f[50:53,x:x+8]=CURSOR
  f[54:58,8:8+g.restored*8]=RESTORED;f[7:10,8:8+min(10,g.order_error)*4]=ERROR
  if g.bad:f[1:4,18:46]=BAD
  return f
class A137(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a137",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.states,self.cursor,self.inverse,self.restored,self.order_error,self.history,self.snapshot=((1,2,3,4,5),0,0,0,15,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.states,self.cursor,self.inverse,self.restored,self.order_error,self.history,self.snapshot=advance((self.states,self.cursor,self.inverse,self.restored,self.order_error,self.history,self.snapshot),a)
  elif a==6:
   if (self.states,self.cursor,self.inverse,self.restored,self.order_error,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
