"""a116 Complement Market -- preserve valuable bundles while routing through swaps."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,MARKET,STALL,ITEM_A,ITEM_B,ITEM_C,BUNDLE,SWAP,VALUE,STRANDED=13,8,7,12,14,10,4,11,9,6
BAD=15
KINDS=(0,1,0,1,2,2)
LEVELS=[
 {"name":"Route Item","seq":(1,)},{"name":"Select Item","seq":(2,)},
 {"name":"Swap Pair","seq":(3,1)},{"name":"Score Bundle","seq":(1,2,3,4,2)},
 {"name":"Protect Complement","seq":(1,3,2,1,4,3,2)},{"name":"Complement Market","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 locations,cursor,phase,value,stranded,history,snapshot=s;loc=list(locations)
 if a==1:loc[cursor]=(loc[cursor]+1)%3;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:
  j=(cursor+1)%6;loc[cursor],loc[j]=loc[j],loc[cursor];phase=(phase+1)%4;history=(history+(3,))[-8:]
 elif a==4:
  value=0;stranded=0
  for station in range(3):
   items=[KINDS[i] for i,p in enumerate(loc) if p==station];value+=3*int(0 in items and 1 in items)+4*(items.count(2)//2);stranded+=int(len(items)==1)
  history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(loc),cursor,phase,value,stranded,history)
 return tuple(loc),cursor,phase,value,stranded,history,snapshot
for x in LEVELS:
 s=((0,0,1,1,2,2),0,0,10,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MARKET;cols=(ITEM_A,ITEM_B,ITEM_C)
  for station in range(3):
   x=8+station*17;f[14:48,x:x+14]=STALL
   members=[i for i,p in enumerate(g.locations) if p==station]
   for row,i in enumerate(members):
    y=18+row*9;f[y:y+7,x+3:x+11]=cols[KINDS[i]]
    if i==g.cursor:f[y-3:y,x+1:x+13]=SWAP
   if len(members)>=2:f[44:48,x+2:x+12]=BUNDLE
  f[7:11,8:8+min(10,g.value)*4]=VALUE;f[53:57,8:8+g.stranded*10]=STRANDED
  if g.bad:f[1:4,18:46]=BAD
  return f
class A116(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a116",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.locations,self.cursor,self.phase,self.value,self.stranded,self.history,self.snapshot=((0,0,1,1,2,2),0,0,10,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.locations,self.cursor,self.phase,self.value,self.stranded,self.history,self.snapshot=advance((self.locations,self.cursor,self.phase,self.value,self.stranded,self.history,self.snapshot),a)
  elif a==6:
   if (self.locations,self.cursor,self.phase,self.value,self.stranded,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
