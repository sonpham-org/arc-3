"""a187 Burst Error -- interleave symbols so contiguous corruption becomes sparse."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,BOARD,SEND_A,SEND_B,BURST,CURSOR,SAFE,CLUSTER,LINK=9,1,12,14,6,13,4,10,8
BAD=15
LEVELS=[
 {"name":"Swap Symbols","seq":(1,)},{"name":"Move Cursor","seq":(2,)},
 {"name":"Move Burst","seq":(3,1)},{"name":"Inspect Damage","seq":(1,2,3,4,2)},
 {"name":"Disperse Burst","seq":(1,3,2,1,4,3,2)},{"name":"Burst Error","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 order,cursor,burst,safe,clusters,history,snapshot=s;o=list(order)
 if a==1:o[cursor],o[(cursor+1)%12]=o[(cursor+1)%12],o[cursor];history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%12;history=(history+(2,))[-8:]
 elif a==3:burst=(burst+2)%12;history=(history+(3,))[-8:]
 elif a==4:
  damaged={o[(burst+i)%12] for i in range(3)};clusters=sum(int(i in damaged and (i-1)%12 in damaged) for i in damaged);safe=3-clusters;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(o),cursor,burst,safe,clusters,history)
 return tuple(o),cursor,burst,safe,clusters,history,snapshot
INITIAL=(0,4,8,1,5,9,2,6,10,3,7,11)
for q in LEVELS:
 s=(INITIAL,0,1,3,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=BOARD
  damaged={(g.burst+i)%12 for i in range(3)}
  for i,source in enumerate(g.order):
   x=7+i*4;y=14;col=BURST if i in damaged else SEND_A if source%2==0 else SEND_B;f[y:y+9,x:x+3]=col;f[31:35,x:x+3]=LINK
   rx=7+source*4;f[40:49,rx:rx+3]=BURST if i in damaged else col
  f[10:13,7+g.cursor*4:10+g.cursor*4]=CURSOR;f[54:58,7:7+g.safe*12]=SAFE;f[54:58,46:46+g.clusters*5]=CLUSTER
  if g.bad:f[1:4,18:46]=BAD
  return f
class A187(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a187",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.order,self.cursor,self.burst,self.safe,self.clusters,self.history,self.snapshot=(INITIAL,0,1,3,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.order,self.cursor,self.burst,self.safe,self.clusters,self.history,self.snapshot=advance((self.order,self.cursor,self.burst,self.safe,self.clusters,self.history,self.snapshot),a)
  elif a==6:
   if (self.order,self.cursor,self.burst,self.safe,self.clusters,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
