"""a198 Shared Resource -- co-design a layout and schedule around one mobile toolhead."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,WORKSHOP,MODULE_A,MODULE_B,MODULE_C,TOOL,TRACK,CURSOR,READY,TRANSIT=7,1,12,14,10,5,8,13,4,6
BAD=15
LEVELS=[
 {"name":"Swap Modules","seq":(1,)},{"name":"Move Cursor","seq":(2,)},
 {"name":"Move Toolhead","seq":(3,1)},{"name":"Check Adjacency","seq":(1,2,3,4,2)},
 {"name":"Schedule Capability","seq":(1,3,2,1,4,3,2)},{"name":"Shared Resource","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 layout,cursor,tool,phase,ready,transit,history,snapshot=s;l=list(layout)
 if a==1:l[cursor],l[(cursor+1)%6]=l[(cursor+1)%6],l[cursor];history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:tool=(tool+1)%6;phase=(phase+1)%3;transit+=1;history=(history+(3,))[-8:]
 elif a==4:ready=sum(int(l[(tool+d)%6]==phase) for d in (-1,0,1));transit=max(0,transit-ready);history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(l),cursor,tool,phase,ready,transit,history)
 return tuple(l),cursor,tool,phase,ready,transit,history,snapshot
for q in LEVELS:
 s=((0,1,2,0,1,2),0,0,0,2,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=WORKSHOP;f[28:35,8:56]=TRACK;cols=(MODULE_A,MODULE_B,MODULE_C)
  for i,v in enumerate(g.layout):
   x=8+i*8;f[12:25,x:x+7]=cols[v]
   if i==g.cursor:f[8:11,x:x+7]=CURSOR
  tx=8+g.tool*8;f[35:48,tx:tx+7]=TOOL;f[51:55,8:8+g.ready*12]=READY;f[55:59,43:43+min(4,g.transit)*4]=TRANSIT
  if g.bad:f[1:4,18:46]=BAD
  return f
class A198(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a198",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.layout,self.cursor,self.tool,self.phase,self.ready,self.transit,self.history,self.snapshot=((0,1,2,0,1,2),0,0,0,2,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.layout,self.cursor,self.tool,self.phase,self.ready,self.transit,self.history,self.snapshot=advance((self.layout,self.cursor,self.tool,self.phase,self.ready,self.transit,self.history,self.snapshot),a)
  elif a==6:
   if (self.layout,self.cursor,self.tool,self.phase,self.ready,self.transit,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
