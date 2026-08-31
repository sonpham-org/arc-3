"""q615 Vivarium Grammar -- compose thermal messages under remembered reciprocity."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VIVARIUM,MOSS,FAUNA,TEMP,GLYPH,TRUST,GOAL,BAD=4,11,5,14,10,6,12,13,15
LEVELS=[{"name":"Thermal Word","seq":(1,)},{"name":"Grouped Fauna","seq":(2,1)},{"name":"Fair Relay","seq":(3,1,2)},{"name":"Temperature Clause","seq":(4,2,3,1)},{"name":"Reciprocal Syntax","seq":(1,3,2,4,2,1)},{"name":"Vivarium Grammar","seq":(2,1,4,3,2,4,1,3,2)}]
def advance(s,a):
 fauna,temp,message,trust,relay,parsed=s;v=list(fauna)
 if a==1:i=(relay+trust)%3;v[i]=(v[i]+1+temp)%6;message=message+((1,i,temp),);trust=min(5,trust+1)
 elif a==2:i=(relay+1)%3;v[i]=(v[i]+2+abs(trust))%6;message=message+((2,i,trust),);trust=max(-3,trust-1)
 elif a==3:relay=(relay+1+int(trust>=0))%3;temp=(temp+relay)%5;message=message+((3,relay,temp),)
 elif a==4:v=v[1:]+v[:1];temp=(temp+2+relay)%5;message=message+((4,tuple(v),temp),)
 elif a==5:parsed=(tuple(v),temp,message[-5:],trust,relay)
 return tuple(v),temp,message,trust,relay,parsed
for x in LEVELS:
 s=((0,2,4),0,(),0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VIVARIUM
  for i,v in enumerate(g.fauna):x=9+i*17;f[9:31,x:x+12]=MOSS;f[24-v*2:29,x+2:x+10]=FAUNA;f[10+g.temp*3:13+g.temp*3,x:x+12]=TEMP
  for i,item in enumerate(g.message[-5:]):x=7+i*10;f[36:42,x:x+8]=GLYPH;f[43:46,x:x+2+item[0]]=TEMP
  lo=min(31,31+g.trust*4);hi=max(31,31+g.trust*4);f[51:55,max(6,lo):min(58,hi+1)]=TRUST;f[56:60,8:8+g.relay*16+10]=GLYPH
  if g.parsed:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q615(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q615",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.fauna=(0,2,4);self.temp=0;self.message=();self.trust=self.relay=0;self.parsed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.fauna,self.temp,self.message,self.trust,self.relay,self.parsed=advance((self.fauna,self.temp,self.message,self.trust,self.relay,self.parsed),a)
  elif a==6:
   if (self.fauna,self.temp,self.message,self.trust,self.relay,self.parsed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
